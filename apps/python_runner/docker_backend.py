"""Runs code in a locked-down, throw-away Docker container. Never on the host itself."""

import contextlib
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.python_runner.config import RunnerConfig
from apps.python_runner.exceptions import RunnerUnavailableError
from apps.python_runner.results import ProcessOutcome

logger = logging.getLogger(__name__)

CONTAINER_LABEL = "python-ai-tutor.runner"
SANDBOX_DIR = "/sandbox"
CONTAINER_USER = "65534:65534"  # nobody:nogroup
TMPFS = "/tmp:rw,nosuid,nodev,noexec,size=16m"
# Time allowed on top of the learner timeout for the container to start and stop.
STARTUP_GRACE_SECONDS = 15
DOCKER_COMMAND_TIMEOUT_SECONDS = 20
# `timeout` exits with 124 when it stopped the command; 137 means SIGKILL.
TIMEOUT_EXIT_CODE = 124
KILLED_EXIT_CODE = 137
# Exit codes used by docker run / timeout when the container or command couldn't start.
INFRASTRUCTURE_EXIT_CODES = frozenset({125, 126, 127})
DOCKER_ERROR_MARKERS = (b"docker:", b"error response from daemon", b"unable to find image")
AVAILABILITY_CACHE_SECONDS = 30
READ_CHUNK_BYTES = 4096
POLL_SECONDS = 0.05


def build_command(
    config: RunnerConfig, name: str, run_id: str, mount_dir: str, argv: list[str]
) -> list[str]:
    """The complete `docker run` invocation. Every isolation setting lives here."""
    return [
        config.docker_binary,
        "run",
        "--rm",
        "--interactive",
        "--pull",
        "never",
        "--name",
        name,
        "--label",
        f"{CONTAINER_LABEL}=1",
        "--label",
        f"{CONTAINER_LABEL}.run={run_id}",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(config.pids_limit),
        "--memory",
        f"{config.memory_mb}m",
        "--memory-swap",
        f"{config.memory_mb}m",
        "--cpus",
        f"{config.cpus:g}",
        "--user",
        CONTAINER_USER,
        "--ulimit",
        "nofile=64:64",
        "--tmpfs",
        TMPFS,
        "--workdir",
        "/tmp",
        "--env",
        "HOME=/tmp",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "PYTHONIOENCODING=utf-8",
        "--mount",
        f"type=bind,source={mount_dir},target={SANDBOX_DIR},readonly",
        config.image,
        "timeout",
        "--kill-after=1",
        f"{config.timeout_seconds:g}",
        "python",
        "-I",
        "-B",
        *argv,
    ]


class DockerBackend:
    def __init__(self, config: RunnerConfig, popen=subprocess.Popen, run=subprocess.run) -> None:
        self.config = config
        self._popen = popen
        self._run = run

    def execute(self, files: dict[str, str], argv: list[str], stdin: str) -> ProcessOutcome:
        """Run ``argv`` with ``files`` mounted read-only at /sandbox and return what happened."""
        run_id = uuid.uuid4().hex
        name = f"pyrun-{run_id}"
        with TemporaryDirectory(prefix="pyrun-", ignore_cleanup_errors=True) as directory:
            self._write_files(Path(directory), files)
            command = build_command(self.config, name, run_id, directory, argv)
            try:
                outcome = self._run_container(command, name, stdin)
            finally:
                self._remove(name)
        logger.debug(
            "Python run %s finished: exit=%s timed_out=%s output_limited=%s duration_ms=%s",
            run_id,
            outcome.exit_code,
            outcome.timed_out,
            outcome.output_limited,
            outcome.duration_ms,
        )
        return outcome

    @staticmethod
    def _write_files(directory: Path, files: dict[str, str]) -> None:
        # The container runs as an unprivileged user, so the files must be world-readable.
        os.chmod(directory, 0o755)
        for filename, text in files.items():
            path = directory / filename
            path.write_text(text, encoding="utf-8")
            os.chmod(path, 0o644)

    def _run_container(self, command: list[str], name: str, stdin: str) -> ProcessOutcome:
        started = time.monotonic()
        try:
            process = self._popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except OSError as exc:
            raise RunnerUnavailableError(f"Could not start the Docker CLI: {exc}") from exc

        limit = self.config.max_output_bytes
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        state = {"total": 0}
        lock = threading.Lock()
        limited = threading.Event()

        def read(stream, key: str) -> None:
            # Keep draining so the pipe never blocks, but store at most `limit` bytes.
            try:
                while chunk := stream.read1(READ_CHUNK_BYTES):
                    with lock:
                        room = limit - state["total"]
                        if room > 0:
                            buffers[key] += chunk[:room]
                        state["total"] += len(chunk)
                        if state["total"] > limit:
                            limited.set()
            except (OSError, ValueError):
                pass

        def write() -> None:
            try:
                process.stdin.write(stdin.encode("utf-8"))
                process.stdin.close()
            except (OSError, ValueError):
                pass

        threads = [
            threading.Thread(target=read, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=read, args=(process.stderr, "stderr"), daemon=True),
            threading.Thread(target=write, daemon=True),
        ]
        for thread in threads:
            thread.start()

        # Host-side backstop; the in-container `timeout` normally stops the program first.
        deadline = started + self.config.timeout_seconds + STARTUP_GRACE_SECONDS
        timed_out = False
        exit_code = None
        while True:
            try:
                exit_code = process.wait(timeout=POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                if limited.is_set():
                    break
                if time.monotonic() > deadline:
                    timed_out = True
                    break
        if exit_code is None:
            self._stop(name, process)
            try:
                exit_code = process.wait(timeout=DOCKER_COMMAND_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                exit_code = None
        for thread in threads:
            thread.join(timeout=5)

        duration_ms = int((time.monotonic() - started) * 1000)
        stdout, stderr = bytes(buffers["stdout"]), bytes(buffers["stderr"])
        if exit_code == TIMEOUT_EXIT_CODE or (
            exit_code == KILLED_EXIT_CODE
            and duration_ms >= self.config.timeout_seconds * 1000
            and not limited.is_set()
        ):
            timed_out = True
        if (
            not timed_out
            and not limited.is_set()
            and exit_code in INFRASTRUCTURE_EXIT_CODES
            and any(marker in stderr.lower() for marker in DOCKER_ERROR_MARKERS)
        ):
            raise RunnerUnavailableError(
                f"Docker could not run the container (exit {exit_code}): "
                f"{stderr.decode('utf-8', 'replace')[:500]}"
            )
        return ProcessOutcome(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            output_limited=limited.is_set(),
        )

    def _docker(self, *args: str) -> subprocess.CompletedProcess | None:
        try:
            return self._run(
                [self.config.docker_binary, *args],
                capture_output=True,
                timeout=DOCKER_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("docker %s failed: %s", args[0], exc)
            return None

    def _stop(self, name: str, process) -> None:
        # Detach first (killing the CLI closes the pipes), then kill the container itself.
        # `docker rm --force` in execute() is the final guarantee.
        with contextlib.suppress(OSError):
            process.kill()
        self._docker("kill", name)

    def _remove(self, name: str) -> None:
        completed = self._docker("rm", "--force", name)
        if completed is not None and completed.returncode != 0:
            message = completed.stderr.decode("utf-8", "replace")
            # With --rm Docker may already be removing (or have removed) the container.
            benign = ("no such container", "already in progress")
            if not any(text in message.lower() for text in benign):
                logger.error("Could not remove runner container %s: %s", name, message[:300])


_availability: dict[str, tuple[float, bool]] = {}


def docker_available(config: RunnerConfig, run=subprocess.run) -> bool:
    """Is the Docker daemon reachable? Cached briefly; never runs learner code."""
    cached = _availability.get(config.docker_binary)
    if cached and time.monotonic() - cached[0] < AVAILABILITY_CACHE_SECONDS:
        return cached[1]
    try:
        completed = run(
            [config.docker_binary, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        available = completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        available = False
    _availability[config.docker_binary] = (time.monotonic(), available)
    return available
