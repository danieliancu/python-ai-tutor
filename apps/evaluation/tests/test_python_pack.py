"""The generic engine against the real Python Foundations exercise pack."""

from collections import Counter
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.results import EvaluationStatus
from apps.exercises.models import Exercise, ResponseType
from apps.exercises.validation import validate_exercise_json


class PythonPackEvaluationTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def exercises(self, response_type: str) -> list[Exercise]:
        exercises = list(Exercise.objects.filter(response_type=response_type))
        self.assertTrue(exercises)
        return exercises

    def test_every_spec_meets_its_contract(self) -> None:
        for exercise in Exercise.objects.all():
            with self.subTest(exercise=exercise.slug):
                validate_exercise_json(
                    exercise.response_type,
                    exercise.content,
                    exercise.evaluation_spec,
                    require_spec=True,
                )

    def test_multiple_choice(self) -> None:
        for exercise in self.exercises(ResponseType.MULTIPLE_CHOICE):
            correct = exercise.evaluation_spec["correct_option"]
            wrong = next(o["id"] for o in exercise.content["options"] if o["id"] != correct)
            with self.subTest(exercise=exercise.slug):
                self.assertEqual(evaluate_exercise(exercise, correct).status, "correct")
                self.assertEqual(evaluate_exercise(exercise, wrong).status, "incorrect")
                self.assertEqual(evaluate_exercise(exercise, "zz").status, "invalid")

    def test_fill_gap(self) -> None:
        for exercise in self.exercises(ResponseType.FILL_GAP):
            with self.subTest(exercise=exercise.slug):
                for answer in exercise.evaluation_spec["accepted_answers"]:
                    self.assertEqual(evaluate_exercise(exercise, answer).status, "correct")
                self.assertEqual(
                    evaluate_exercise(exercise, "definitely not this").status, "incorrect"
                )

    def test_code_is_recognised_but_not_run(self) -> None:
        for exercise in self.exercises(ResponseType.CODE):
            with self.subTest(exercise=exercise.slug):
                result = evaluate_exercise(exercise, exercise.evaluation_spec["reference_solution"])
                self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
                self.assertEqual(result.evaluator, "code")

    def test_text_rubrics_need_review(self) -> None:
        for exercise in self.exercises(ResponseType.TEXT):
            with self.subTest(exercise=exercise.slug):
                result = evaluate_exercise(exercise, "1. Load tasks\n2. Add a task")
                self.assertEqual(result.status, EvaluationStatus.REVIEW_REQUIRED)
                self.assertEqual(result.evaluator, "rubric")

    def test_whole_pack_evaluates_without_errors(self) -> None:
        allowed = {
            ResponseType.MULTIPLE_CHOICE: {"correct", "incorrect"},
            ResponseType.FILL_GAP: {"incorrect"},
            ResponseType.CODE: {"unsupported"},
            ResponseType.TEXT: {"review_required"},
        }
        statuses = Counter()
        for exercise in Exercise.objects.all():
            status = evaluate_exercise(exercise, "a").status
            statuses[status] += 1
            with self.subTest(exercise=exercise.slug):
                self.assertIn(status, allowed[exercise.response_type])
        self.assertEqual(sum(statuses.values()), Exercise.objects.count())
