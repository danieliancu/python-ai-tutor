"""Evaluates Python CODE exercises by running the learner's code in the isolated runner."""

import logging
from collections.abc import Callable

from django.core.exceptions import ValidationError

from apps.evaluation import results
from apps.evaluation.evaluators.base import config_error, content_of, spec_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise
from apps.exercises.validation import validate_exercise_json
from apps.python_runner.comparison import json_equal
from apps.python_runner.config import RunnerConfig, get_runner_config
from apps.python_runner.exceptions import RunnerUnavailableError, SourceRejected
from apps.python_runner.results import RunStatus
from apps.python_runner.runner import PythonRunner, validate_source

logger = logging.getLogger(__name__)

MESSAGE_FAILED = "That code didn't pass the checks yet."
MESSAGE_DISABLED = "Code evaluation is not available yet."
SOURCE_MESSAGES = {
    "invalid_answer_type": "Submit your code as text.",
    "empty_answer": "Write some code first.",
    "invalid_source": "Your code contains characters that can't be run.",
    "source_too_large": "Your code is too long to run.",
}
# Run outcomes that are the learner's responsibility. Anything else is infrastructure.
LEARNER_FAILURES = frozenset(
    {
        RunStatus.RUNTIME_ERROR,
        RunStatus.TIMEOUT,
        RunStatus.OUTPUT_LIMIT,
        RunStatus.INVALID_RESULT,
    }
)


def normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class PythonCodeEvaluator:
    name = "python_code"

    def __init__(
        self,
        config_provider: Callable[[], RunnerConfig] = get_runner_config,
        runner_factory: Callable[[RunnerConfig], PythonRunner] = PythonRunner,
    ) -> None:
        self._config_provider = config_provider
        self._runner_factory = runner_factory

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        config = self._config_provider()
        if not config.enabled:
            return results.unsupported(self.name, "python_runner_disabled", MESSAGE_DISABLED)

        spec = self._checked_spec(exercise)
        try:
            source = validate_source(answer, config)
        except SourceRejected as rejected:
            return results.invalid(self.name, rejected.reason, SOURCE_MESSAGES[rejected.reason])

        runner = self._runner_factory(config)
        if spec["strategy"] == "stdout":
            result = self._evaluate_stdout(runner, source, spec["tests"])
        else:
            result = self._evaluate_function(runner, source, spec)
        logger.debug(
            "Evaluated exercise %s with %s: %s (%s)",
            exercise.pk,
            spec["strategy"],
            result.status,
            result.diagnostics.get("reason", "-"),
        )
        return result

    @staticmethod
    def _checked_spec(exercise: Exercise) -> dict:
        spec = spec_of(exercise)
        try:
            validate_exercise_json(
                exercise.response_type, content_of(exercise), spec, require_spec=True
            )
        except ValidationError as exc:
            raise config_error(exercise, f"invalid code evaluation spec: {exc}") from exc
        return spec

    def _failed(self, reason: str, error_type: str | None = None) -> EvaluationResult:
        details = {"error_type": error_type} if error_type else {}
        return results.incorrect(self.name, reason, MESSAGE_FAILED, details)

    @staticmethod
    def _check_status(status: RunStatus) -> None:
        if status != RunStatus.SUCCESS and status not in LEARNER_FAILURES:
            raise RunnerUnavailableError(f"Runner reported {status}")

    def _evaluate_stdout(self, runner: PythonRunner, source: str, tests: list) -> EvaluationResult:
        for test in tests:
            run = runner.run_program(source, test["stdin"])
            self._check_status(run.status)
            if run.status != RunStatus.SUCCESS:
                return self._failed(str(run.status), run.error_type)
            if normalise_newlines(run.stdout) != normalise_newlines(test["expected_stdout"]):
                return self._failed("output_mismatch")
        return results.correct(self.name)

    def _evaluate_function(self, runner: PythonRunner, source: str, spec: dict) -> EvaluationResult:
        tests = spec["tests"]
        if spec.get("run_tests_in_one_process") is True:
            batches = [list(range(len(tests)))]
        else:
            # A fresh container per test, so one call can't affect the next.
            batches = [[index] for index in range(len(tests))]

        for batch in batches:
            calls = [(tests[index]["args"], tests[index]["kwargs"]) for index in batch]
            replies = runner.run_functions(source, spec["function_name"], calls)
            if len(replies) != len(batch):
                raise RunnerUnavailableError("Runner returned the wrong number of results")
            for index, reply in zip(batch, replies, strict=True):
                self._check_status(reply.status)
                if reply.status != RunStatus.SUCCESS:
                    return self._failed(reply.error or str(reply.status), reply.error_type)
                if not json_equal(reply.value, tests[index]["expected"]):
                    return self._failed("wrong_result")
        return results.correct(self.name)
