from django.test import SimpleTestCase

from apps.attempts.mistakes import (
    MISTAKE_CODES,
    extract_mistakes_from_result,
    is_safe_details,
    safe_diagnostics,
)
from apps.evaluation import results
from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.results import EvaluationResult
from apps.evaluation.tests import helpers as eval_helpers
from apps.python_runner.evaluator import PythonCodeEvaluator
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import (
    ENABLED,
    FakeBackend,
    code_exercise,
    function_calls,
    function_spec,
    harness_reply,
    outcome,
    stdout_spec,
)

SPEC_STDOUT = stdout_spec(("", "hi\n"))
SPEC_FUNCTION = function_spec("f", ([], {}, 1))


def python_result(spec, answer, handler=None):
    backend = FakeBackend(handler or (lambda *a: outcome("hi\n")))
    evaluator = PythonCodeEvaluator(
        config_provider=lambda: ENABLED, runner_factory=lambda c: PythonRunner(c, backend)
    )
    return evaluator.evaluate(code_exercise(spec), answer)


def reply(value):
    return lambda files, argv, stdin: harness_reply(stdin, [value for _ in function_calls(stdin)])


def codes(result: EvaluationResult) -> list[str]:
    return [mistake["code"] for mistake in extract_mistakes_from_result(result)]


class ExtractionFromRealEvaluatorsTests(SimpleTestCase):
    def test_every_evaluator_reason_is_extracted(self) -> None:
        cases = {
            "wrong_option": evaluate_exercise(eval_helpers.mcq(), "opt-a"),
            "invalid_option": evaluate_exercise(eval_helpers.mcq(), "opt-z"),
            "incorrect_value": evaluate_exercise(eval_helpers.fill_gap(), "<"),
            "case_mismatch": evaluate_exercise(eval_helpers.fill_gap(answers=("True",)), "TRUE"),
            "invalid_numeric_input": evaluate_exercise(eval_helpers.numeric(), "twelve"),
            "invalid_answer_type": evaluate_exercise(eval_helpers.fill_gap(), 5),
            "empty_answer": evaluate_exercise(eval_helpers.fill_gap(), "  "),
            "output_mismatch": python_result(SPEC_STDOUT, "print('x')", lambda *a: outcome("x\n")),
            "runtime_error": python_result(
                SPEC_STDOUT,
                "1/0",
                lambda *a: outcome(stderr="ZeroDivisionError: division by zero", exit_code=1),
            ),
            "timeout": python_result(
                SPEC_STDOUT, "while True: pass", lambda *a: outcome(exit_code=124, timed_out=True)
            ),
            "output_limit": python_result(
                SPEC_STDOUT, "print", lambda *a: outcome("x", exit_code=137, output_limited=True)
            ),
            "wrong_result": python_result(SPEC_FUNCTION, "x", reply({"ok": True, "value": 2})),
            "missing_function": python_result(
                SPEC_FUNCTION, "x", reply({"ok": False, "error": "missing_function"})
            ),
            "not_callable": python_result(
                SPEC_FUNCTION, "x", reply({"ok": False, "error": "not_callable"})
            ),
            "non_serializable_result": python_result(
                SPEC_FUNCTION, "x", reply({"ok": False, "error": "non_serializable_result"})
            ),
            "invalid_result": python_result(SPEC_FUNCTION, "x", lambda *a: outcome("")),
            "invalid_source": python_result(SPEC_STDOUT, "print(1)\x00"),
            "source_too_large": python_result(SPEC_STDOUT, "#" * 70_000),
        }
        self.assertEqual(set(cases), MISTAKE_CODES)
        for code, result in cases.items():
            with self.subTest(code=code):
                self.assertEqual(codes(result), [code])

    def test_runtime_errors_keep_only_the_exception_class(self) -> None:
        result = python_result(
            SPEC_STDOUT,
            "1/0",
            lambda *a: outcome(stderr="ZeroDivisionError: division by zero", exit_code=1),
        )
        self.assertEqual(
            extract_mistakes_from_result(result),
            [{"code": "runtime_error", "details": {"error_type": "ZeroDivisionError"}}],
        )

    def test_no_mistakes_without_a_learner_error(self) -> None:
        for result in (
            evaluate_exercise(eval_helpers.mcq(), "opt-b"),
            evaluate_exercise(eval_helpers.exercise("translation"), "Hello"),
            evaluate_exercise(eval_helpers.exercise("speaking"), "x"),
            python_result(SPEC_STDOUT, "print('hi')"),
            results.unsupported("code", "python_runner_disabled"),
        ):
            with self.subTest(status=result.status):
                self.assertEqual(extract_mistakes_from_result(result), [])

    def test_unknown_reasons_are_ignored(self) -> None:
        self.assertEqual(codes(results.incorrect("future", "partially_right")), [])
        self.assertEqual(codes(results.invalid("future", "weird thing")), [])


class SafetyHelperTests(SimpleTestCase):
    def test_safe_diagnostics_keeps_only_codes(self) -> None:
        self.assertEqual(
            safe_diagnostics(
                {
                    "reason": "runtime_error",
                    "error_type": "KeyError",
                    "expected": "secret",
                    "tests": [1],
                }
            ),
            {"reason": "runtime_error", "error_type": "KeyError"},
        )
        self.assertEqual(safe_diagnostics({"reason": "not a code!"}), {})
        self.assertEqual(safe_diagnostics({"reason": 5}), {})

    def test_is_safe_details(self) -> None:
        self.assertTrue(is_safe_details({}))
        self.assertTrue(is_safe_details({"error_type": "TypeError"}))
        for value in ({"correct_option": "b"}, {"error_type": "x y"}, [], None, "x"):
            with self.subTest(value=value):
                self.assertFalse(is_safe_details(value))
