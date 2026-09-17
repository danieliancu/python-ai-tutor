"""Runs learner Python code through an isolated backend and interprets what happened."""

import json
import re
import secrets
from functools import cache
from pathlib import Path
from typing import Protocol

from apps.python_runner.config import RunnerConfig, get_runner_config
from apps.python_runner.docker_backend import DockerBackend, docker_available
from apps.python_runner.exceptions import SourceRejected
from apps.python_runner.fixtures import FIXTURE_DIR, validate_fixture_files
from apps.python_runner.results import (
    FunctionCallResult,
    ProcessOutcome,
    PythonRunResult,
    RunStatus,
)

LEARNER_FILE = "learner.py"
HARNESS_FILE = "harness.py"
BOOTSTRAP_FILE = "bootstrap.py"
SANDBOX_SOURCE_DIR = Path(__file__).resolve().parent / "sandbox"
HARNESS_PATH = SANDBOX_SOURCE_DIR / "harness.py"
ERROR_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
TRACEBACK_ERROR_LINE = re.compile(r"^([A-Za-z_][\w.]*)(?::|$)")
HARNESS_ERRORS = {
    "missing_function": RunStatus.RUNTIME_ERROR,
    "not_callable": RunStatus.RUNTIME_ERROR,
    "runtime_error": RunStatus.RUNTIME_ERROR,
    "non_serializable_result": RunStatus.INVALID_RESULT,
}


class Backend(Protocol):
    def execute(self, files: dict[str, str], argv: list[str], stdin: str) -> ProcessOutcome: ...


@cache
def harness_source() -> str:
    return HARNESS_PATH.read_text(encoding="utf-8")


@cache
def bootstrap_source() -> str:
    return (SANDBOX_SOURCE_DIR / BOOTSTRAP_FILE).read_text(encoding="utf-8")


def sandbox_launch(
    files: dict[str, str], script: str, extra_files: dict[str, str] | None
) -> tuple[dict[str, str], list[str]]:
    """Files and argv for running ``script``; fixture files go through the bootstrap."""
    if not extra_files:
        return files, [f"/sandbox/{script}"]
    fixtures = validate_fixture_files(extra_files)
    files = {**files, BOOTSTRAP_FILE: bootstrap_source()}
    files.update({f"{FIXTURE_DIR}/{name}": text for name, text in fixtures.items()})
    return files, [f"/sandbox/{BOOTSTRAP_FILE}", f"/sandbox/{script}"]


def validate_source(source: object, config: RunnerConfig) -> str:
    """Basic sanity checks only. The container, not this function, is the security boundary."""
    if not isinstance(source, str):
        raise SourceRejected("invalid_answer_type")
    if not source.strip():
        raise SourceRejected("empty_answer")
    if "\x00" in source:
        raise SourceRejected("invalid_source")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        raise SourceRejected("invalid_source") from None
    if size > config.max_source_bytes:
        raise SourceRejected("source_too_large")
    return source


def safe_error_type(name: object) -> str | None:
    """An exception class name that is safe to keep in diagnostics, or None."""
    if isinstance(name, str) and ERROR_TYPE_PATTERN.match(name):
        return name
    return None


def error_type_from_stderr(stderr: str) -> str | None:
    """The exception class from the last line of a Python traceback, e.g. 'ZeroDivisionError'."""
    for line in reversed(stderr.splitlines()):
        if line.strip():
            match = TRACEBACK_ERROR_LINE.match(line)
            return safe_error_type(match.group(1).rsplit(".", 1)[-1]) if match else None
    return None


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "replace")


class PythonRunner:
    def __init__(self, config: RunnerConfig, backend: Backend | None = None) -> None:
        self.config = config
        self.backend = backend or DockerBackend(config)

    def run_program(
        self, source: str, stdin: str = "", extra_files: dict[str, str] | None = None
    ) -> PythonRunResult:
        """Run the source as a script with ``stdin`` and report its output.

        ``extra_files`` are private fixture files placed in the program's working directory.
        """
        validate_source(source, self.config)
        files, argv = sandbox_launch({LEARNER_FILE: source}, LEARNER_FILE, extra_files)
        outcome = self.backend.execute(files, argv, stdin)
        stderr = _decode(outcome.stderr)
        if outcome.output_limited:
            status = RunStatus.OUTPUT_LIMIT
        elif outcome.timed_out:
            status = RunStatus.TIMEOUT
        elif outcome.exit_code == 0:
            status = RunStatus.SUCCESS
        else:
            status = RunStatus.RUNTIME_ERROR
        return PythonRunResult(
            status=status,
            stdout=_decode(outcome.stdout),
            stderr=stderr,
            return_code=outcome.exit_code,
            duration_ms=outcome.duration_ms,
            error_type=error_type_from_stderr(stderr)
            if status == RunStatus.RUNTIME_ERROR
            else None,
        )

    def run_functions(
        self,
        source: str,
        function_name: str,
        calls: list[tuple[list, dict]],
        extra_files: dict[str, str] | None = None,
    ) -> list[FunctionCallResult]:
        """Call the learner's function once per (args, kwargs), in order, in one container.

        The container receives only the function name and arguments; results come back as
        plain JSON and are compared by the caller.
        """
        validate_source(source, self.config)
        marker = f"@@RUNNER-RESULT-{secrets.token_hex(16)}@@"
        request = json.dumps(
            {
                "function_name": function_name,
                "calls": [{"args": list(args), "kwargs": dict(kwargs)} for args, kwargs in calls],
                "marker": marker,
            }
        )
        files, argv = sandbox_launch(
            {LEARNER_FILE: source, HARNESS_FILE: harness_source()}, HARNESS_FILE, extra_files
        )
        outcome = self.backend.execute(files, argv, request)
        if outcome.output_limited:
            return [FunctionCallResult(RunStatus.OUTPUT_LIMIT)] * len(calls)
        if outcome.timed_out:
            return [FunctionCallResult(RunStatus.TIMEOUT)] * len(calls)
        replies = self._read_envelope(_decode(outcome.stdout), marker, len(calls))
        if replies is None:
            return [FunctionCallResult(RunStatus.INVALID_RESULT, error="invalid_result")] * len(
                calls
            )
        return [self._call_result(reply) for reply in replies]

    def run_function(
        self, source: str, function_name: str, args: list, kwargs: dict
    ) -> FunctionCallResult:
        return self.run_functions(source, function_name, [(args, kwargs)])[0]

    @staticmethod
    def _read_envelope(stdout: str, marker: str, expected_count: int) -> list[dict] | None:
        for line in reversed(stdout.splitlines()):
            if not line.startswith(marker):
                continue
            try:
                envelope = json.loads(line[len(marker) :])
            except ValueError:
                return None
            replies = envelope.get("results") if isinstance(envelope, dict) else None
            if (
                isinstance(replies, list)
                and len(replies) == expected_count
                and all(
                    isinstance(reply, dict) and isinstance(reply.get("ok"), bool)
                    for reply in replies
                )
            ):
                return replies
            return None
        return None

    @staticmethod
    def _call_result(reply: dict) -> FunctionCallResult:
        if reply["ok"]:
            if "value" not in reply:
                return FunctionCallResult(RunStatus.INVALID_RESULT, error="invalid_result")
            return FunctionCallResult(RunStatus.SUCCESS, value=reply["value"])
        error = reply.get("error")
        status = HARNESS_ERRORS.get(error)
        if status is None:
            return FunctionCallResult(RunStatus.INVALID_RESULT, error="invalid_result")
        return FunctionCallResult(
            status, error=error, error_type=safe_error_type(reply.get("error_type"))
        )


def python_runner_available(config: RunnerConfig | None = None) -> bool:
    """True when the runner is enabled and Docker answers. Runs no learner code."""
    config = config or get_runner_config()
    return config.enabled and docker_available(config)
