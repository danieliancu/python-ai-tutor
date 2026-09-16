from pathlib import Path

from django.test import SimpleTestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.exceptions import EvaluationConfigurationError
from apps.evaluation.results import EvaluationStatus
from apps.evaluation.tests import helpers

RUBRIC = {"strategy": "rubric", "criteria": ["Has 4 to 6 steps."]}


class PendingEvaluatorTests(SimpleTestCase):
    def test_code_is_unsupported_and_never_run(self) -> None:
        marker = Path(__file__).with_name("should-never-exist.txt")
        answer = f"open({str(marker)!r}, 'w').write('ran')\nprint('hi')"
        exercise = helpers.exercise(
            "code",
            {"language": "python", "starter_code": ""},
            {"strategy": "stdout", "tests": [{"stdin": "", "expected_stdout": "hi\n"}]},
        )
        for submitted in (answer, "", None, 42):
            with self.subTest(answer=submitted):
                result = evaluate_exercise(exercise, submitted)
                self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
                self.assertEqual(result.evaluator, "code")
                self.assertEqual(result.message, "Code evaluation is not available yet.")
                self.assertIsNone(result.is_correct)
                self.assertIsNone(result.score)
        self.assertFalse(marker.exists())

    def test_text_like_answers_await_review(self) -> None:
        cases = [
            ("text", RUBRIC, "rubric"),
            ("translation", {"reference_answers": ["Good morning!"]}, "translation"),
            ("translation", {}, "translation"),
            ("math_expression", {"equivalent_to": "5*x"}, "math_expression"),
        ]
        for response_type, spec, evaluator in cases:
            exercise = helpers.exercise(response_type, {}, spec)
            with self.subTest(response_type=response_type, spec=spec):
                result = evaluate_exercise(exercise, "Good morning!")
                self.assertEqual(result.status, EvaluationStatus.REVIEW_REQUIRED)
                self.assertEqual(result.evaluator, evaluator)
                self.assertIsNone(result.is_correct)
                self.assertIsNone(result.score)
                self.assertEqual(result.message, "This answer needs further evaluation.")

    def test_exact_reference_answer_is_still_not_marked_correct(self) -> None:
        exercise = helpers.exercise("translation", {}, {"reference_answers": ["Good morning!"]})
        self.assertEqual(
            evaluate_exercise(exercise, "Good morning!").status, EvaluationStatus.REVIEW_REQUIRED
        )

    def test_text_like_answers_must_be_text(self) -> None:
        for response_type, spec in (("text", RUBRIC), ("translation", {}), ("math_expression", {})):
            exercise = helpers.exercise(response_type, {}, spec)
            for answer, reason in (
                ("", "empty_answer"),
                ("  ", "empty_answer"),
                (None, "invalid_answer_type"),
                (5, "invalid_answer_type"),
            ):
                with self.subTest(response_type=response_type, answer=answer):
                    result = evaluate_exercise(exercise, answer)
                    self.assertEqual(result.status, EvaluationStatus.INVALID)
                    self.assertEqual(result.diagnostics["reason"], reason)

    def test_text_needs_a_rubric_spec(self) -> None:
        for spec in ({}, {"strategy": "exact"}, []):
            exercise = helpers.exercise("text", {}, spec)
            with self.subTest(spec=spec), self.assertRaises(EvaluationConfigurationError):
                evaluate_exercise(exercise, "My plan")

    def test_audio_types_are_unsupported(self) -> None:
        for response_type in ("speaking", "listening"):
            exercise = helpers.exercise(response_type)
            with self.subTest(response_type=response_type):
                result = evaluate_exercise(exercise, "anything")
                self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
                self.assertEqual(result.evaluator, response_type)
                self.assertIsNone(result.is_correct)
