"""Attempts against the real Python Foundations pack (Docker-free)."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.attempts.models import AttemptStatus
from apps.attempts.services import record_attempt
from apps.attempts.tests.helpers import AttemptFixtures
from apps.curriculum.models import World
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment
from apps.python_runner.tests.fakes import outcome


class PythonPackAttemptTests(AttemptFixtures, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def setUp(self) -> None:
        super().setUp()
        world = World.objects.get(slug="python-foundations")
        self.pack_enrollment = Enrollment.objects.create(learner=self.profile, world=world)

    def attempt(self, slug: str, answer):
        exercise = Exercise.objects.get(slug=slug)
        return record_attempt(user=self.user, exercise=exercise, answer=answer)

    def test_multiple_choice(self) -> None:
        wrong = self.attempt("ten-or-more", "a")
        right = self.attempt("ten-or-more", "b")
        self.assertEqual((wrong.status, right.status), ("incorrect", "correct"))
        self.assertEqual((wrong.attempt_number, right.attempt_number), (1, 2))
        self.assertEqual(wrong.enrollment, self.pack_enrollment)
        self.assertEqual(list(wrong.mistakes.values_list("code", flat=True)), ["wrong_option"])

    def test_fill_gap(self) -> None:
        self.assertEqual(self.attempt("one-to-five", "6").status, AttemptStatus.CORRECT)
        wrong = self.attempt("one-to-five", "5")
        self.assertEqual(wrong.status, AttemptStatus.INCORRECT)
        self.assertEqual(list(wrong.mistakes.values_list("code", flat=True)), ["incorrect_value"])

    def test_code_with_runner_disabled_is_unsupported(self) -> None:
        attempt = self.attempt("greater-than-ten", "print(18)")
        self.assertEqual(attempt.status, AttemptStatus.UNSUPPORTED)
        self.assertIsNone(attempt.is_correct)

    def test_code_with_runner_down_is_unavailable(self) -> None:
        self.break_python_runner()
        with self.assertLogs("apps.attempts.services", level="ERROR"):
            attempt = self.attempt("greater-than-ten", "print(18)")
        self.assertEqual(attempt.status, AttemptStatus.UNAVAILABLE)
        self.assertFalse(attempt.mistakes.exists())

    def test_code_through_the_python_evaluator(self) -> None:
        exercise = Exercise.objects.get(slug="greater-than-ten")
        expected = exercise.evaluation_spec["tests"][0]["expected_stdout"]
        backend = self.use_python_backend(lambda *a: outcome(expected))
        correct = self.attempt("greater-than-ten", "for n in [18, 25, 13]:\n    print(n)\n")
        self.assertEqual(correct.status, AttemptStatus.CORRECT)
        self.assertEqual(correct.evaluator, "python_code")
        self.assertFalse(correct.mistakes.exists())

        backend.handler = lambda *a: outcome("4\n7\n")
        wrong = self.attempt("greater-than-ten", "print(4)\nprint(7)\n")
        self.assertEqual(wrong.status, AttemptStatus.INCORRECT)
        self.assertEqual(wrong.attempt_number, 2)
        self.assertEqual(list(wrong.mistakes.values_list("code", flat=True)), ["output_mismatch"])
        self.assertNotIn("reference_solution", str(backend.requests))
