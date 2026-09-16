"""Internal execution results.

These describe what happened when code ran. Whether an answer is correct is decided later
and reported with the generic ``EvaluationResult``.
"""

from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    SUCCESS = "success"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    INVALID_RESULT = "invalid_result"
    RUNNER_UNAVAILABLE = "runner_unavailable"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class ProcessOutcome:
    """What a backend observed while running one container."""

    exit_code: int | None
    stdout: bytes
    stderr: bytes
    duration_ms: int
    timed_out: bool = False
    output_limited: bool = False


@dataclass(frozen=True)
class PythonRunResult:
    """One program run (the stdout strategy)."""

    status: RunStatus
    stdout: str
    stderr: str
    return_code: int | None
    duration_ms: int
    error_type: str | None = None


@dataclass(frozen=True)
class FunctionCallResult:
    """One function call made by the harness (the function strategy).

    ``error`` is a machine-readable code such as ``missing_function``; ``value`` holds the
    JSON-compatible return value when the call succeeded.
    """

    status: RunStatus
    value: object = None
    error: str | None = None
    error_type: str | None = None
