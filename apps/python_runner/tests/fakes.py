"""Test doubles. No Docker, and no learner code is ever executed by these."""

import json
from collections.abc import Callable

from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.python_runner.config import RunnerConfig
from apps.python_runner.results import ProcessOutcome

ENABLED = RunnerConfig(backend="docker")
DISABLED = RunnerConfig()


def outcome(stdout="", stderr="", exit_code=0, **flags) -> ProcessOutcome:
    return ProcessOutcome(
        exit_code=exit_code,
        stdout=stdout.encode(),
        stderr=stderr.encode(),
        duration_ms=5,
        **flags,
    )


def harness_reply(stdin: str, replies: list[dict], noise: str = "") -> ProcessOutcome:
    """What the harness would print for ``replies``, using the marker from the request."""
    marker = json.loads(stdin)["marker"]
    return outcome(noise + "\n" + marker + json.dumps({"results": replies}) + "\n")


class FakeBackend:
    """Records every request; ``handler(files, argv, stdin)`` decides the outcome."""

    def __init__(self, handler: Callable[[dict, list, str], ProcessOutcome]) -> None:
        self.handler = handler
        self.requests: list[dict] = []

    def execute(self, files: dict[str, str], argv: list[str], stdin: str) -> ProcessOutcome:
        self.requests.append({"files": dict(files), "argv": list(argv), "stdin": stdin})
        return self.handler(files, argv, stdin)


def function_calls(stdin: str) -> list[dict]:
    return json.loads(stdin)["calls"]


def code_exercise(spec: dict, language: str = "python", pk: int = 11) -> Exercise:
    return Exercise(
        pk=pk,
        title="Code",
        slug="code",
        prompt="Write code.",
        order=1,
        response_type=ResponseType.CODE,
        learning_mode=LearningMode.CREATE,
        content={"language": language, "starter_code": "# start\n"},
        evaluation_spec=spec,
        is_published=True,
    )


def stdout_spec(*tests: tuple[str, str], **extra) -> dict:
    return {
        "strategy": "stdout",
        "tests": [{"stdin": stdin, "expected_stdout": out} for stdin, out in tests],
        **extra,
    }


def function_spec(name: str, *tests: tuple[list, dict, object], **extra) -> dict:
    return {
        "strategy": "function",
        "function_name": name,
        "tests": [{"args": a, "kwargs": k, "expected": e} for a, k, e in tests],
        **extra,
    }
