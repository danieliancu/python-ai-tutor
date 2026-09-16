import io
import subprocess
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.python_runner import docker_backend
from apps.python_runner.config import RunnerConfig
from apps.python_runner.docker_backend import DockerBackend, docker_available
from apps.python_runner.exceptions import RunnerUnavailableError

CONFIG = RunnerConfig(backend="docker", timeout_seconds=0.2, max_output_bytes=1024)


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", exit_code=0, hangs=False):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.stdin = io.BytesIO()
        self.exit_code = exit_code
        self.hangs = hangs
        self.killed = False
        self.received = b""

    def wait(self, timeout=None):
        if self.hangs and not self.killed:
            raise subprocess.TimeoutExpired("docker", timeout)
        return 137 if self.killed else self.exit_code

    def kill(self):
        self.killed = True


class FakeDocker:
    """Stands in for subprocess.Popen / subprocess.run around the docker CLI."""

    def __init__(self, process=None, popen_error=None):
        self.process = process or FakeProcess()
        self.popen_error = popen_error
        self.commands: list[list[str]] = []
        self.cli_calls: list[list[str]] = []

    def popen(self, command, **kwargs):
        self.assertions(kwargs)
        self.commands.append(command)
        self.mount_dir = next(
            part.split("source=")[1].split(",")[0] for part in command if "source=" in part
        )
        self.files_seen = {
            path.name: path.read_text(encoding="utf-8") for path in Path(self.mount_dir).iterdir()
        }
        if self.popen_error:
            raise self.popen_error
        original_close = self.process.stdin.close

        def close():
            self.process.received = self.process.stdin.getvalue()
            original_close()

        self.process.stdin.close = close
        return self.process

    @staticmethod
    def assertions(kwargs):
        assert "shell" not in kwargs, "docker must never be started through a shell"

    def run(self, command, **kwargs):
        self.cli_calls.append(command)
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def backend(self, config=CONFIG):
        return DockerBackend(config, popen=self.popen, run=self.run)


def execute(docker: FakeDocker, stdin: str = "", config=CONFIG):
    return docker.backend(config).execute(
        {"learner.py": "print('hi')\n"}, ["/sandbox/learner.py"], stdin
    )


class DockerBackendTests(SimpleTestCase):
    def test_success_returns_output_and_cleans_up(self) -> None:
        docker = FakeDocker(FakeProcess(stdout=b"hi\n", stderr=b""))
        result = execute(docker, stdin="Cluj\n")

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, b"hi\n")
        self.assertFalse(result.timed_out or result.output_limited)
        self.assertEqual(docker.process.received, b"Cluj\n")
        self.assertEqual(docker.files_seen, {"learner.py": "print('hi')\n"})
        self.assertFalse(Path(docker.mount_dir).exists())
        name = docker.commands[0][docker.commands[0].index("--name") + 1]
        self.assertIn(["docker", "rm", "--force", name], docker.cli_calls)

    def test_every_run_gets_a_unique_container(self) -> None:
        docker = FakeDocker()
        execute(docker)
        docker.process = FakeProcess()
        execute(docker)
        names = [cmd[cmd.index("--name") + 1] for cmd in docker.commands]
        self.assertEqual(len(set(names)), 2)
        self.assertTrue(all(name.startswith("pyrun-") and len(name) == 38 for name in names))

    def test_output_is_capped(self) -> None:
        docker = FakeDocker(FakeProcess(stdout=b"x" * 5000, hangs=True))
        result = execute(docker)
        self.assertTrue(result.output_limited)
        self.assertEqual(len(result.stdout), CONFIG.max_output_bytes)
        self.assertTrue(docker.process.killed)
        self.assertTrue(any(call[1] == "kill" for call in docker.cli_calls))
        self.assertFalse(Path(docker.mount_dir).exists())

    def test_stdout_and_stderr_share_the_cap(self) -> None:
        docker = FakeDocker(FakeProcess(stdout=b"o" * 600, stderr=b"e" * 600, exit_code=1))
        result = execute(docker)
        self.assertTrue(result.output_limited)
        self.assertLessEqual(len(result.stdout) + len(result.stderr), CONFIG.max_output_bytes)

    def test_host_timeout_kills_the_container(self) -> None:
        docker = FakeDocker(FakeProcess(hangs=True))
        with mock.patch.object(docker_backend, "STARTUP_GRACE_SECONDS", 0):
            result = execute(docker)
        self.assertTrue(result.timed_out)
        self.assertTrue(docker.process.killed)
        self.assertTrue(any(call[1] == "kill" for call in docker.cli_calls))
        self.assertTrue(any(call[1] == "rm" for call in docker.cli_calls))
        self.assertFalse(Path(docker.mount_dir).exists())

    def test_in_container_timeout_exit_code(self) -> None:
        result = execute(FakeDocker(FakeProcess(exit_code=124)))
        self.assertTrue(result.timed_out)

    def test_missing_docker_binary_is_an_infrastructure_error(self) -> None:
        docker = FakeDocker(popen_error=FileNotFoundError("docker"))
        with self.assertRaises(RunnerUnavailableError):
            execute(docker)
        self.assertTrue(any(call[1] == "rm" for call in docker.cli_calls))
        self.assertFalse(Path(docker.mount_dir).exists())

    def test_docker_failures_are_infrastructure_errors(self) -> None:
        for stderr in (
            b"docker: Error response from daemon: No such image: python:3.11-slim.",
            b"Cannot connect... docker: error during connect",
            b"Unable to find image 'python:3.11-slim' locally",
        ):
            docker = FakeDocker(FakeProcess(stderr=stderr, exit_code=125))
            with self.subTest(stderr=stderr), self.assertRaises(RunnerUnavailableError):
                execute(docker)
            self.assertFalse(Path(docker.mount_dir).exists())

    def test_learner_exit_codes_are_not_infrastructure_errors(self) -> None:
        for code in (1, 2, 125, 126, 127):
            docker = FakeDocker(FakeProcess(stderr=b"Traceback ...\nSystemExit", exit_code=code))
            with self.subTest(code=code):
                result = execute(docker)
                self.assertEqual(result.exit_code, code)

    def test_cleanup_failures_are_logged_not_raised(self) -> None:
        docker = FakeDocker(FakeProcess(stdout=b"ok\n"))

        def failing_run(command, **kwargs):
            if command[1] == "rm":
                return subprocess.CompletedProcess(command, 1, b"", b"permission denied")
            return subprocess.CompletedProcess(command, 0, b"", b"")

        backend = DockerBackend(CONFIG, popen=docker.popen, run=failing_run)
        with self.assertLogs("apps.python_runner.docker_backend", level="ERROR"):
            result = backend.execute({"learner.py": "x"}, ["/sandbox/learner.py"], "")
        self.assertEqual(result.stdout, b"ok\n")

    def test_logs_never_contain_the_source(self) -> None:
        secret_source = "print('TOP-SECRET-SOURCE')\n"
        docker = FakeDocker(FakeProcess(stdout=b"x"))
        with self.assertLogs("apps.python_runner.docker_backend", level="DEBUG") as logs:
            docker.backend().execute({"learner.py": secret_source}, ["/sandbox/learner.py"], "")
        self.assertNotIn("TOP-SECRET-SOURCE", "\n".join(logs.output))


class DockerAvailabilityTests(SimpleTestCase):
    def setUp(self) -> None:
        docker_backend._availability.clear()
        self.addCleanup(docker_backend._availability.clear)

    def test_available_when_daemon_answers(self) -> None:
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, b"29.0", b"")

        self.assertTrue(docker_available(CONFIG, run=run))
        self.assertTrue(docker_available(CONFIG, run=run))
        self.assertEqual(len(calls), 1, "the answer is cached briefly")
        self.assertEqual(calls[0][:2], ["docker", "info"])

    def test_unavailable_when_daemon_or_binary_missing(self) -> None:
        def down(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, b"", b"cannot connect")

        def missing(command, **kwargs):
            raise FileNotFoundError("docker")

        self.assertFalse(docker_available(CONFIG, run=down))
        docker_backend._availability.clear()
        self.assertFalse(docker_available(CONFIG, run=missing))
