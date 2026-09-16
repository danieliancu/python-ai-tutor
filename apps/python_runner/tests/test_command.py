from django.test import SimpleTestCase

from apps.python_runner.config import RunnerConfig
from apps.python_runner.docker_backend import build_command

CONFIG = RunnerConfig(
    backend="docker",
    image="python:3.11-slim",
    timeout_seconds=3,
    memory_mb=128,
    cpus=0.5,
    pids_limit=64,
)


def command(argv=("/sandbox/learner.py",), config=CONFIG) -> list[str]:
    return build_command(config, "pyrun-abc", "abc", "/tmp/pyrun-xyz", list(argv))


def option(cmd: list[str], flag: str) -> list[str]:
    return [cmd[i + 1] for i, part in enumerate(cmd[:-1]) if part == flag]


class DockerCommandTests(SimpleTestCase):
    def setUp(self) -> None:
        self.cmd = command()
        self.text = " ".join(self.cmd)

    def test_starts_a_fresh_removable_container(self) -> None:
        self.assertEqual(self.cmd[:3], ["docker", "run", "--rm"])
        self.assertEqual(option(self.cmd, "--pull"), ["never"])
        self.assertEqual(option(self.cmd, "--name"), ["pyrun-abc"])
        self.assertIn("python-ai-tutor.runner=1", option(self.cmd, "--label"))

    def test_isolation_flags(self) -> None:
        self.assertEqual(option(self.cmd, "--network"), ["none"])
        self.assertIn("--read-only", self.cmd)
        self.assertEqual(option(self.cmd, "--cap-drop"), ["ALL"])
        self.assertEqual(option(self.cmd, "--security-opt"), ["no-new-privileges"])
        self.assertEqual(option(self.cmd, "--user"), ["65534:65534"])

    def test_resource_limits(self) -> None:
        self.assertEqual(option(self.cmd, "--memory"), ["128m"])
        self.assertEqual(option(self.cmd, "--memory-swap"), ["128m"])
        self.assertEqual(option(self.cmd, "--cpus"), ["0.5"])
        self.assertEqual(option(self.cmd, "--pids-limit"), ["64"])
        self.assertEqual(option(self.cmd, "--ulimit"), ["nofile=64:64"])

    def test_writable_space_is_a_small_tmpfs(self) -> None:
        self.assertEqual(option(self.cmd, "--tmpfs"), ["/tmp:rw,nosuid,nodev,noexec,size=16m"])
        self.assertEqual(option(self.cmd, "--workdir"), ["/tmp"])

    def test_only_the_run_directory_is_mounted_read_only(self) -> None:
        self.assertEqual(
            option(self.cmd, "--mount"),
            ["type=bind,source=/tmp/pyrun-xyz,target=/sandbox,readonly"],
        )
        self.assertNotIn("--volume", self.cmd)
        self.assertNotIn("-v", self.cmd)

    def test_minimal_environment(self) -> None:
        self.assertEqual(
            option(self.cmd, "--env"),
            ["HOME=/tmp", "PYTHONDONTWRITEBYTECODE=1", "PYTHONIOENCODING=utf-8"],
        )
        self.assertNotIn("--env-file", self.cmd)
        for secret in ("DJANGO", "SECRET", "DATABASE", ".env", "docker.sock"):
            self.assertNotIn(secret, self.text)

    def test_nothing_dangerous_is_requested(self) -> None:
        for flag in (
            "--privileged",
            "--cap-add",
            "--network=host",
            "--pid",
            "--ipc",
            "--device",
            "--userns",
            "--volumes-from",
        ):
            self.assertNotIn(flag, self.cmd)
        self.assertNotIn("host", option(self.cmd, "--network"))
        self.assertNotIn("root", option(self.cmd, "--user"))

    def test_program_runs_under_timeout_in_isolated_mode(self) -> None:
        image_index = self.cmd.index("python:3.11-slim")
        self.assertEqual(
            self.cmd[image_index + 1 :],
            ["timeout", "--kill-after=1", "3", "python", "-I", "-B", "/sandbox/learner.py"],
        )

    def test_uses_configured_binary_image_and_limits(self) -> None:
        config = RunnerConfig(
            backend="docker",
            image="python@sha256:1234",
            timeout_seconds=1.5,
            memory_mb=64,
            cpus=1,
            pids_limit=16,
            docker_binary="/usr/local/bin/docker",
        )
        cmd = command(config=config)
        self.assertEqual(cmd[0], "/usr/local/bin/docker")
        self.assertIn("python@sha256:1234", cmd)
        self.assertEqual(option(cmd, "--memory"), ["64m"])
        self.assertEqual(option(cmd, "--cpus"), ["1"])
        self.assertEqual(option(cmd, "--pids-limit"), ["16"])
        self.assertIn("1.5", cmd)

    def test_names_are_per_run(self) -> None:
        first = build_command(CONFIG, "pyrun-1", "1", "/a", [])
        second = build_command(CONFIG, "pyrun-2", "2", "/b", [])
        self.assertNotEqual(option(first, "--name"), option(second, "--name"))
