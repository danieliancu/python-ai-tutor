"""Deterministic checks for Python project stages, run only in the isolated Python runner."""

import secrets
from collections.abc import Callable

from apps.evaluation import results
from apps.evaluation.results import EvaluationResult
from apps.projects.evaluation.spec import stage_spec_errors
from apps.projects.evaluation.structure import check_structure
from apps.python_runner.comparison import json_equal
from apps.python_runner.config import RunnerConfig, get_runner_config
from apps.python_runner.evaluator import SOURCE_MESSAGES, normalise_newlines
from apps.python_runner.exceptions import RunnerUnavailableError, SourceRejected
from apps.python_runner.results import RunStatus
from apps.python_runner.runner import PythonRunner, validate_source

EVALUATOR = "python_project"
FAILED_MESSAGE = "Your program doesn't pass this stage's checks yet."
STRUCTURE_MESSAGE = "Your program is missing something this stage needs."
LEARNER_FAILURES = frozenset(
    {RunStatus.RUNTIME_ERROR, RunStatus.TIMEOUT, RunStatus.OUTPUT_LIMIT, RunStatus.INVALID_RESULT}
)


class ProjectSpecError(RunnerUnavailableError):
    """The stage itself is misconfigured. Treated like unavailable checking, never as wrong."""


def _check_status(status: RunStatus) -> None:
    if status != RunStatus.SUCCESS and status not in LEARNER_FAILURES:
        raise RunnerUnavailableError(f"Runner reported {status}")


def _failed(reason: str, error_type: str | None = None) -> EvaluationResult:
    details = {"error_type": error_type} if error_type else {}
    return results.incorrect(EVALUATOR, reason, FAILED_MESSAGE, details)


class PythonProjectEvaluator:
    name = EVALUATOR

    def __init__(
        self,
        config_provider: Callable[[], RunnerConfig] = get_runner_config,
        runner_factory: Callable[[RunnerConfig], PythonRunner] = PythonRunner,
    ) -> None:
        self.config_provider = config_provider
        self.runner_factory = runner_factory

    def evaluate(self, spec: dict, source: object) -> EvaluationResult:
        config = self.config_provider()
        problems = stage_spec_errors(spec)
        if problems:
            raise ProjectSpecError("; ".join(problems))
        try:
            validate_source(source, config)
        except SourceRejected as exc:
            return results.invalid(self.name, exc.reason, SOURCE_MESSAGES[exc.reason])

        problem = check_structure(source, spec.get("requires"))
        if problem is not None:
            if problem.reason == "syntax_error":
                return _failed("syntax_error", "SyntaxError")
            return results.incorrect(
                self.name, problem.reason, STRUCTURE_MESSAGE, {"missing": problem.missing}
            )

        if not config.enabled:
            return results.unsupported(
                self.name, "python_runner_disabled", "Project checking is not available yet."
            )
        runner = self.runner_factory(config)
        fixtures = spec.get("fixtures") or None
        if spec["strategy"] == "stdout":
            return self._stdout(runner, spec, source, fixtures)
        return self._functions(runner, spec, source, fixtures)

    def _stdout(self, runner, spec, source, fixtures) -> EvaluationResult:
        for test in spec["tests"]:
            program, marker = source, None
            if test.get("driver"):
                # Only what the private driver prints is compared, so the learner's own
                # top-level output never gets in the way.
                marker = f"@@CHECK-{secrets.token_hex(12)}@@"
                program = f"{source.rstrip()}\n\n\nprint({marker!r})\n{test['driver']}"
            run = runner.run_program(program, test["stdin"], extra_files=fixtures)
            _check_status(run.status)
            if run.status != RunStatus.SUCCESS:
                return _failed(str(run.status), run.error_type)
            output = normalise_newlines(run.stdout)
            if marker is not None:
                _, found, output = output.rpartition(marker + "\n")
                if not found:
                    return _failed("output_mismatch")
            if output != normalise_newlines(test["expected_stdout"]):
                return _failed("output_mismatch")
        return results.correct(self.name)

    def _functions(self, runner, spec, source, fixtures) -> EvaluationResult:
        tests = spec["tests"]
        batches = [tests] if spec.get("run_tests_in_one_process") else [[test] for test in tests]
        for batch in batches:
            replies = runner.run_functions(
                source,
                spec["function_name"],
                [(test["args"], test["kwargs"]) for test in batch],
                extra_files=fixtures,
            )
            if len(replies) != len(batch):
                raise RunnerUnavailableError("Runner returned an unexpected number of results")
            for test, reply in zip(batch, replies, strict=True):
                _check_status(reply.status)
                if reply.status != RunStatus.SUCCESS:
                    return _failed(reply.error or str(reply.status), reply.error_type)
                if not json_equal(reply.value, test["expected"]):
                    return _failed("wrong_result")
        return results.correct(self.name)
