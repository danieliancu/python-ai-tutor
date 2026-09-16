from django.test import SimpleTestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.exceptions import EvaluationConfigurationError
from apps.evaluation.results import EvaluationStatus
from apps.evaluation.tests import helpers


class FillGapEvaluatorTests(SimpleTestCase):
    def evaluate(self, answer, **kwargs):
        return evaluate_exercise(helpers.fill_gap(**kwargs), answer)

    def test_exact_answer_is_correct(self) -> None:
        result = self.evaluate(">=")
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        self.assertEqual((result.score, result.is_correct), (1.0, True))

    def test_any_accepted_answer_is_correct(self) -> None:
        for answer in ('"-"', "'-'"):
            with self.subTest(answer=answer):
                result = self.evaluate(answer, answers=['"-"', "'-'"])
                self.assertEqual(result.status, EvaluationStatus.CORRECT)

    def test_wrong_answer_is_incorrect(self) -> None:
        for answer in (">", "<=", "=>", "> ="):
            with self.subTest(answer=answer):
                result = self.evaluate(answer)
                self.assertEqual(result.status, EvaluationStatus.INCORRECT)
                self.assertEqual((result.score, result.is_correct), (0.0, False))
                self.assertEqual(result.diagnostics["reason"], "incorrect_value")

    def test_surrounding_whitespace_is_ignored(self) -> None:
        self.assertEqual(self.evaluate("  >=\t\n").status, EvaluationStatus.CORRECT)
        # Whitespace in the configured answer is trimmed as well.
        self.assertEqual(self.evaluate("len", answers=[" len "]).status, EvaluationStatus.CORRECT)

    def test_case_sensitive_by_default(self) -> None:
        result = self.evaluate("TRUE", answers=["True"])
        self.assertEqual(result.status, EvaluationStatus.INCORRECT)
        self.assertEqual(result.diagnostics["reason"], "case_mismatch")
        self.assertEqual(
            self.evaluate("True", answers=["True"], case_sensitive=True).status,
            EvaluationStatus.CORRECT,
        )

    def test_case_insensitive(self) -> None:
        for answer in ("bottom", "BOTTOM", "Bottom"):
            with self.subTest(answer=answer):
                result = self.evaluate(answer, answers=["bottom"], case_sensitive=False)
                self.assertEqual(result.status, EvaluationStatus.CORRECT)
        result = self.evaluate("top", answers=["bottom"], case_sensitive=False)
        self.assertEqual(result.diagnostics["reason"], "incorrect_value")

    def test_unicode_casefold(self) -> None:
        self.assertEqual(
            self.evaluate("STRASSE", answers=["straße"], case_sensitive=False).status,
            EvaluationStatus.CORRECT,
        )
        self.assertEqual(
            self.evaluate("STRASSE", answers=["straße"]).diagnostics["reason"], "case_mismatch"
        )

    def test_malformed_answers_are_invalid(self) -> None:
        for answer, reason in (
            (None, "invalid_answer_type"),
            (5, "invalid_answer_type"),
            ([">="], "invalid_answer_type"),
            ("", "empty_answer"),
            ("   ", "empty_answer"),
        ):
            with self.subTest(answer=answer):
                result = self.evaluate(answer)
                self.assertEqual(result.status, EvaluationStatus.INVALID)
                self.assertIsNone(result.is_correct)
                self.assertEqual(result.diagnostics["reason"], reason)

    def test_misconfigured_exercises_raise(self) -> None:
        broken = [
            helpers.exercise("fill_gap", {"template": "__"}, {}),
            helpers.fill_gap(answers=()),
            helpers.fill_gap(answers=("",)),
            helpers.fill_gap(answers=("  ",)),
            helpers.fill_gap(answers=(">=", 3)),
            helpers.exercise("fill_gap", {}, {"accepted_answers": ">="}),
            helpers.fill_gap(case_sensitive="yes"),
        ]
        for exercise in broken:
            with (
                self.subTest(spec=exercise.evaluation_spec),
                self.assertRaises(EvaluationConfigurationError),
            ):
                evaluate_exercise(exercise, ">=")

    def test_result_never_reveals_accepted_answers(self) -> None:
        secret = "zebra-quartz-7"
        for answer in ("wrong", "ZEBRA-QUARTZ-7", "", secret):
            result = self.evaluate(answer, answers=[secret])
            with self.subTest(answer=answer):
                self.assertNotIn("accepted_answers", repr(result))
                if answer != secret:
                    self.assertNotIn(secret, repr(result).casefold())
