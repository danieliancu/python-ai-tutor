from decimal import Decimal

from django.test import SimpleTestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.evaluators.numeric import to_decimal
from apps.evaluation.exceptions import EvaluationConfigurationError
from apps.evaluation.results import EvaluationStatus
from apps.evaluation.tests import helpers

CORRECT = EvaluationStatus.CORRECT
INCORRECT = EvaluationStatus.INCORRECT
INVALID = EvaluationStatus.INVALID


class NumericEvaluatorTests(SimpleTestCase):
    def status(self, answer, expected=12.5, **spec):
        return evaluate_exercise(helpers.numeric(expected, **spec), answer).status

    def test_exact_values(self) -> None:
        self.assertEqual(self.status(12, expected=12), CORRECT)
        self.assertEqual(self.status(12.0, expected=12), CORRECT)
        self.assertEqual(self.status(12.5), CORRECT)
        self.assertEqual(self.status("12.5"), CORRECT)
        self.assertEqual(self.status("12.50"), CORRECT)
        self.assertEqual(self.status(" 12.5 "), CORRECT)
        self.assertEqual(self.status("1.25e1"), CORRECT)

    def test_exact_comparison_has_no_float_surprises(self) -> None:
        self.assertEqual(self.status(0.1 + 0.2, expected=0.3), INCORRECT)
        self.assertEqual(self.status("0.3", expected=0.3), CORRECT)
        self.assertEqual(self.status(0.1 + 0.2, expected=0.3, tolerance=1e-9), CORRECT)

    def test_tolerance(self) -> None:
        self.assertEqual(self.status("12.59", tolerance=0.1), CORRECT)
        self.assertEqual(self.status("12.6", tolerance=0.1), CORRECT)
        self.assertEqual(self.status("12.4", tolerance=0.1), CORRECT)
        self.assertEqual(self.status("12.61", tolerance=0.1), INCORRECT)
        self.assertEqual(self.status("12.51", tolerance=0), INCORRECT)

    def test_incorrect_result_shape(self) -> None:
        result = evaluate_exercise(helpers.numeric(), "13")
        self.assertEqual(result.status, INCORRECT)
        self.assertEqual((result.score, result.is_correct), (0.0, False))
        self.assertEqual(dict(result.diagnostics), {"reason": "incorrect_value"})

    def test_negative_numbers_and_zero(self) -> None:
        self.assertEqual(self.status("-3.5", expected=-3.5), CORRECT)
        self.assertEqual(self.status("3.5", expected=-3.5), INCORRECT)
        self.assertEqual(self.status(0, expected=0), CORRECT)
        self.assertEqual(self.status("-0", expected=0), CORRECT)
        self.assertEqual(self.status("0.0", expected=0), CORRECT)
        self.assertEqual(self.status("0.001", expected=0), INCORRECT)

    def test_malformed_answers_are_invalid(self) -> None:
        for answer in (
            "twelve",
            "12,5",
            "12.5cm",
            "",
            "   ",
            "0x10",
            "1" * 101,
            "1e999999999",
            None,
            [12.5],
            {"value": 12.5},
        ):
            with self.subTest(answer=answer):
                result = evaluate_exercise(helpers.numeric(), answer)
                self.assertEqual(result.status, INVALID)
                self.assertEqual(result.message, "Enter a valid number.")
                self.assertEqual(result.diagnostics["reason"], "invalid_numeric_input")

    def test_booleans_are_not_numbers(self) -> None:
        self.assertEqual(self.status(True, expected=1), INVALID)
        self.assertEqual(self.status(False, expected=0), INVALID)

    def test_non_finite_values_are_invalid(self) -> None:
        for answer in (
            float("nan"),
            float("inf"),
            float("-inf"),
            "NaN",
            "nan",
            "sNaN",
            "Infinity",
            "-Infinity",
            "inf",
        ):
            with self.subTest(answer=answer):
                self.assertEqual(self.status(answer), INVALID)

    def test_misconfigured_exercises_raise(self) -> None:
        for spec in (
            {},
            {"expected": "12.5"},
            {"expected": True},
            {"expected": None},
            {"expected": float("nan")},
            {"expected": float("inf")},
            {"expected": 12.5, "tolerance": -0.1},
            {"expected": 12.5, "tolerance": "0.1"},
            {"expected": 12.5, "tolerance": float("inf")},
            {"expected": 12.5, "tolerance": False},
        ):
            exercise = helpers.exercise("numeric", {}, spec)
            with self.subTest(spec=spec), self.assertRaises(EvaluationConfigurationError):
                evaluate_exercise(exercise, "12.5")

    def test_result_never_reveals_expected_value(self) -> None:
        for answer in ("1", "abc", "98765.4321"):
            result = evaluate_exercise(helpers.numeric(98765.4321, tolerance=0.5), answer)
            with self.subTest(answer=answer):
                for secret in ("98765", "expected", "tolerance", "0.5"):
                    if answer == "98765.4321" and secret == "98765":
                        continue
                    self.assertNotIn(secret, repr(result))

    def test_to_decimal(self) -> None:
        self.assertEqual(to_decimal(0.1, allow_text=False), Decimal("0.1"))
        self.assertIsNone(to_decimal("1", allow_text=False))
        self.assertEqual(to_decimal("1", allow_text=True), Decimal("1"))
        self.assertIsNone(to_decimal("1e-101", allow_text=True))
