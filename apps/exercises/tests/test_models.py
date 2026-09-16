from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.curriculum.models import Lesson
from apps.curriculum.tests.helpers import make_lesson
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain


class ExerciseModelTests(TestCase):
    def setUp(self) -> None:
        self.lesson = make_lesson_chain("Python Foundations")

    def test_belongs_to_lesson(self) -> None:
        exercise = make_exercise(self.lesson, title="Print big numbers")
        self.assertEqual(exercise.lesson, self.lesson)
        self.assertEqual(list(self.lesson.exercises.all()), [exercise])
        self.assertEqual(str(exercise), f"{self.lesson.title}: Print big numbers")

    def test_defaults(self) -> None:
        exercise = make_exercise(self.lesson, content={}, evaluation_spec={}, is_published=False)
        fresh = Exercise.objects.get(pk=exercise.pk)
        self.assertEqual(fresh.instructions, "")
        self.assertEqual(fresh.evaluation_spec, {})
        self.assertIsNone(fresh.target_seconds)
        self.assertFalse(fresh.is_published)

    def test_json_round_trip(self) -> None:
        spec = {
            "strategy": "function",
            "function_name": "largest",
            "tests": [{"args": [[3, 12]], "kwargs": {}, "expected": 12}],
            "note": {"nested": [1.5, None, True]},
        }
        exercise = make_exercise(self.lesson, evaluation_spec=spec)
        self.assertEqual(Exercise.objects.get(pk=exercise.pk).evaluation_spec, spec)

    def test_ordering_follows_the_curriculum_then_order(self) -> None:
        later_lesson = make_lesson(self.lesson.concept, order=self.lesson.order + 1)
        c = make_exercise(later_lesson, order=1)
        b = make_exercise(self.lesson, order=2)
        a = make_exercise(self.lesson, order=1)
        self.assertEqual(list(Exercise.objects.all()), [a, b, c])

    def test_same_slug_allowed_in_different_lessons(self) -> None:
        other = make_lesson(self.lesson.concept)
        make_exercise(self.lesson, slug="shared")
        make_exercise(other, slug="shared")
        self.assertEqual(Exercise.objects.filter(slug="shared").count(), 2)

    def test_deleting_lesson_deletes_exercises(self) -> None:
        make_exercise(self.lesson)
        Lesson.objects.filter(pk=self.lesson.pk).delete()
        self.assertFalse(Exercise.objects.exists())

    def test_save_validates_json(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            make_exercise(self.lesson, response_type=ResponseType.MULTIPLE_CHOICE, content={})
        self.assertIn("content", ctx.exception.message_dict)
        self.assertFalse(Exercise.objects.exists())


class ExerciseConstraintTests(TestCase):
    """Normal saves validate first, so these go through bulk_create to reach the database."""

    def setUp(self) -> None:
        self.lesson = make_lesson_chain()
        make_exercise(self.lesson, slug="first", order=1)

    def build(self, **fields) -> Exercise:
        values = {
            "lesson": self.lesson,
            "title": "Another",
            "slug": "another",
            "prompt": "Prompt",
            "order": 2,
            "response_type": ResponseType.TEXT,
            "learning_mode": LearningMode.CREATE,
        }
        values.update(fields)
        return Exercise(**values)

    def assert_db_rejects(self, **fields) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            Exercise.objects.bulk_create([self.build(**fields)])

    def assert_model_rejects(self, field: str, **fields) -> None:
        with self.assertRaises(ValidationError) as ctx:
            self.build(**fields).save()
        self.assertIn(field, ctx.exception.message_dict)

    def test_duplicate_slug_in_lesson(self) -> None:
        self.assert_db_rejects(slug="first")
        self.assert_model_rejects("__all__", slug="first")

    def test_duplicate_order_in_lesson(self) -> None:
        self.assert_db_rejects(order=1)
        self.assert_model_rejects("__all__", order=1)

    def test_order_must_be_positive(self) -> None:
        self.assert_db_rejects(order=0)
        self.assert_model_rejects("order", order=0)

    def test_target_seconds_must_be_positive_when_given(self) -> None:
        self.assert_db_rejects(target_seconds=0)
        self.assert_model_rejects("target_seconds", target_seconds=0)
        self.build(target_seconds=None).save()
        self.build(slug="third", order=3, target_seconds=90).save()
        self.assertEqual(Exercise.objects.count(), 3)

    def test_response_type_must_be_known(self) -> None:
        self.assert_db_rejects(response_type="essay")
        self.assert_model_rejects("response_type", response_type="essay")

    def test_learning_mode_must_be_known(self) -> None:
        self.assert_db_rejects(learning_mode="memorise")
        self.assert_model_rejects("learning_mode", learning_mode="memorise")
