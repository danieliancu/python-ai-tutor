from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.attempts.models import AttemptMistake, AttemptStatus, ExerciseAttempt
from apps.attempts.tests.helpers import AttemptFixtures
from apps.exercises.models import Exercise


class AttemptModelTests(AttemptFixtures, TestCase):
    def build(self, **fields) -> ExerciseAttempt:
        values = {
            "enrollment": self.enrollment,
            "exercise": self.mcq,
            "attempt_number": 1,
            "submitted_answer": "opt-a",
            "status": AttemptStatus.INCORRECT,
            "score": 0.0,
            "is_correct": False,
            "evaluator": "multiple_choice",
            "message": "That answer isn't correct yet.",
            "diagnostics": {"reason": "wrong_option"},
        }
        values.update(fields)
        return ExerciseAttempt(**values)

    def test_create_attempt_and_mistake(self) -> None:
        attempt = self.build()
        attempt.save()
        mistake = AttemptMistake.objects.create(attempt=attempt, code="wrong_option")
        self.assertEqual(list(attempt.mistakes.all()), [mistake])
        self.assertEqual(attempt.hint_level, 0)
        self.assertFalse(attempt.used_explanation or attempt.used_solution)
        self.assertIsNone(attempt.duration_seconds)
        self.assertIsNotNone(attempt.submitted_at)
        self.assertEqual(str(attempt), f"learner · {self.mcq.title} · #1")
        self.assertEqual(str(mistake), f"wrong_option (attempt {attempt.pk})")

    def test_answer_accepts_any_json_shape(self) -> None:
        for number, answer in enumerate(
            ["code", 12.5, 3, True, None, [1, "a"], {"k": [None]}, "", [], {}], start=1
        ):
            with self.subTest(answer=answer):
                self.build(attempt_number=number, submitted_answer=answer).save()
                stored = ExerciseAttempt.objects.get(attempt_number=number).submitted_answer
                self.assertEqual(stored, answer)

    def test_numbers_are_unique_per_enrollment_and_exercise(self) -> None:
        self.build().save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExerciseAttempt.objects.bulk_create([self.build()])
        with self.assertRaises(ValidationError):
            self.build().save()
        self.build(exercise=self.gap).save()
        self.build(enrollment=self.english_enrollment).save()
        self.assertEqual(ExerciseAttempt.objects.count(), 3)

    def test_mistake_codes_are_unique_per_attempt(self) -> None:
        attempt = self.build()
        attempt.save()
        AttemptMistake.objects.create(attempt=attempt, code="wrong_option")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttemptMistake.objects.bulk_create(
                [AttemptMistake(attempt=attempt, code="wrong_option")]
            )

    def test_database_checks(self) -> None:
        for fields in (
            {"attempt_number": 0},
            {"status": "passed"},
            {"score": 1.5},
            {"score": -0.1},
            {"hint_level": 11},
            {"duration_seconds": 86_401},
        ):
            with self.subTest(**fields), self.assertRaises(IntegrityError), transaction.atomic():
                ExerciseAttempt.objects.bulk_create([self.build(**fields)])

    def test_model_validation(self) -> None:
        for field, value in (
            ("attempt_number", 0),
            ("status", "passed"),
            ("score", 2.0),
            ("hint_level", 11),
            ("duration_seconds", 86_401),
            ("diagnostics", {"reason": "wrong_option", "expected": "b"}),
            ("diagnostics", {"reason": "has spaces"}),
            ("diagnostics", ["wrong_option"]),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError) as ctx:
                    self.build(**{field: value}).save()
                self.assertIn(field, ctx.exception.message_dict)
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_mistake_details_must_be_safe(self) -> None:
        attempt = self.build()
        attempt.save()
        for details in ({"expected_stdout": "x"}, {"error_type": "Bad Name!"}, ["x"]):
            with self.subTest(details=details), self.assertRaises(ValidationError):
                AttemptMistake.objects.create(
                    attempt=attempt, code="runtime_error", details=details
                )
        AttemptMistake.objects.create(
            attempt=attempt, code="runtime_error", details={"error_type": "ZeroDivisionError"}
        )

    def test_ordering_is_newest_first(self) -> None:
        first = self.build()
        first.save()
        second = self.build(attempt_number=2)
        second.save()
        self.assertEqual(list(ExerciseAttempt.objects.all()), [second, first])

    def test_history_is_protected_and_mistakes_cascade(self) -> None:
        attempt = self.build()
        attempt.save()
        AttemptMistake.objects.create(attempt=attempt, code="wrong_option")
        with self.assertRaises(ProtectedError):
            Exercise.objects.filter(pk=self.mcq.pk).delete()
        with self.assertRaises(ProtectedError):
            self.enrollment.delete()
        attempt.delete()
        self.assertFalse(AttemptMistake.objects.exists())
