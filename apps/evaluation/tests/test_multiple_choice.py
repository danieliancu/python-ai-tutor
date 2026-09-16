from django.test import SimpleTestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.exceptions import EvaluationConfigurationError
from apps.evaluation.results import EvaluationStatus
from apps.evaluation.tests import helpers


class MultipleChoiceEvaluatorTests(SimpleTestCase):
    def status(self, answer, exercise=None):
        return evaluate_exercise(exercise or helpers.mcq(), answer)

    def test_correct_answer(self) -> None:
        result = self.status("opt-b")
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        self.assertEqual((result.score, result.is_correct), (1.0, True))
        self.assertEqual(result.message, "Correct.")
        self.assertEqual(dict(result.diagnostics), {})

    def test_incorrect_answer(self) -> None:
        result = self.status("opt-a")
        self.assertEqual(result.status, EvaluationStatus.INCORRECT)
        self.assertEqual((result.score, result.is_correct), (0.0, False))
        self.assertEqual(dict(result.diagnostics), {"reason": "wrong_option"})

    def test_surrounding_whitespace_is_ignored(self) -> None:
        self.assertEqual(self.status("  opt-b\n").status, EvaluationStatus.CORRECT)
        self.assertEqual(self.status(" opt-c ").status, EvaluationStatus.INCORRECT)

    def test_unknown_or_malformed_answers_are_invalid(self) -> None:
        for answer in ("opt-z", "", "   ", "OPT-B", "Option opt-b", None, 1, ["opt-b"], True):
            with self.subTest(answer=answer):
                result = self.status(answer)
                self.assertEqual(result.status, EvaluationStatus.INVALID)
                self.assertIsNone(result.score)
                self.assertIsNone(result.is_correct)
                self.assertEqual(result.diagnostics["reason"], "invalid_option")

    def test_misconfigured_exercises_raise(self) -> None:
        broken = [
            helpers.mcq(correct=None),
            helpers.mcq(correct=""),
            helpers.mcq(correct=2),
            helpers.mcq(correct="opt-missing"),
            helpers.exercise("multiple_choice", {"options": []}, {"correct_option": "a"}),
            helpers.exercise("multiple_choice", {}, {"correct_option": "a"}),
            helpers.exercise("multiple_choice", {"options": [{"id": 1, "text": "x"}]}, {}),
            helpers.exercise("multiple_choice", {"options": [{"id": "a"}]}, []),
        ]
        for exercise in broken:
            with (
                self.subTest(content=exercise.content, spec=exercise.evaluation_spec),
                self.assertRaises(EvaluationConfigurationError),
            ):
                evaluate_exercise(exercise, "opt-b")

    def test_result_never_reveals_the_correct_option(self) -> None:
        for answer in ("opt-a", "opt-z", "opt-b"):
            result = self.status(answer)
            text = repr(result)
            with self.subTest(answer=answer):
                self.assertNotIn("correct_option", text)
                if answer != "opt-b":
                    self.assertNotIn("opt-b", text)
