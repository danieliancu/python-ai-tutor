from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.tests.helpers import make_user
from apps.attempts import services
from apps.attempts.models import AttemptMistake, AttemptStatus, ExerciseAttempt
from apps.attempts.services import (
    UNAVAILABLE_MESSAGE,
    AttemptInputError,
    record_attempt,
    resolve_enrollment,
)
from apps.attempts.tests.helpers import SECRET_GAP, SECRET_OPTION, AttemptFixtures
from apps.exercises.models import Exercise
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile
from apps.python_runner.tests.fakes import outcome


class RecordAttemptStatusTests(AttemptFixtures, TestCase):
    def test_correct(self) -> None:
        attempt = self.record(self.mcq, SECRET_OPTION, hint_level=1, duration_seconds=40)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, AttemptStatus.CORRECT)
        self.assertEqual((attempt.score, attempt.is_correct), (1.0, True))
        self.assertEqual(attempt.evaluator, "multiple_choice")
        self.assertEqual(attempt.message, "Correct.")
        self.assertEqual(attempt.diagnostics, {})
        self.assertEqual((attempt.hint_level, attempt.duration_seconds), (1, 40))
        self.assertEqual(attempt.submitted_answer, SECRET_OPTION)
        self.assertEqual(attempt.enrollment, self.enrollment)
        self.assertFalse(attempt.mistakes.exists())

    def test_incorrect_with_mistake(self) -> None:
        attempt = self.record(self.gap, "wrong", used_explanation=True)
        self.assertEqual(attempt.status, AttemptStatus.INCORRECT)
        self.assertEqual((attempt.score, attempt.is_correct), (0.0, False))
        self.assertTrue(attempt.used_explanation)
        self.assertEqual(attempt.diagnostics, {"reason": "incorrect_value"})
        self.assertEqual(
            list(attempt.mistakes.values_list("code", "details")), [("incorrect_value", {})]
        )

    def test_invalid_still_records_a_mistake(self) -> None:
        attempt = self.record(self.numeric, "about twelve")
        self.assertEqual(attempt.status, AttemptStatus.INVALID)
        self.assertIsNone(attempt.score)
        self.assertIsNone(attempt.is_correct)
        self.assertEqual(
            list(attempt.mistakes.values_list("code", flat=True)), ["invalid_numeric_input"]
        )

    def test_review_required(self) -> None:
        attempt = self.record(self.translation, "Hello")
        self.assertEqual(attempt.status, AttemptStatus.REVIEW_REQUIRED)
        self.assertEqual((attempt.score, attempt.is_correct), (None, None))
        self.assertFalse(attempt.mistakes.exists())

    def test_unsupported_while_runner_disabled(self) -> None:
        attempt = self.record(self.code, "print('hi')")
        self.assertEqual(attempt.status, AttemptStatus.UNSUPPORTED)
        self.assertEqual(attempt.evaluator, "python_code")
        self.assertEqual(attempt.diagnostics, {"reason": "python_runner_disabled"})
        self.assertFalse(attempt.mistakes.exists())

    def test_runner_failure_is_unavailable_not_incorrect(self) -> None:
        self.break_python_runner()
        with self.assertLogs("apps.attempts.services", level="ERROR") as logs:
            attempt = self.record(self.code, "print('hi')")
        self.assertEqual(attempt.status, AttemptStatus.UNAVAILABLE)
        self.assertEqual((attempt.score, attempt.is_correct), (None, None))
        self.assertEqual(attempt.message, UNAVAILABLE_MESSAGE)
        self.assertEqual(attempt.diagnostics, {"reason": "evaluation_unavailable"})
        self.assertEqual(attempt.evaluator, "code")
        self.assertFalse(attempt.mistakes.exists())
        self.assertNotIn("print('hi')", "\n".join(logs.output))

    def test_misconfigured_exercise_is_unavailable_not_incorrect(self) -> None:
        Exercise.objects.filter(pk=self.numeric.pk).update(evaluation_spec={"expected": "x"})
        self.numeric.refresh_from_db()
        with self.assertLogs("apps.attempts.services", level="ERROR"):
            attempt = self.record(self.numeric, "12")
        self.assertEqual(attempt.status, AttemptStatus.UNAVAILABLE)
        self.assertEqual(attempt.evaluator, "numeric")

    def test_python_code_through_the_evaluator(self) -> None:
        backend = self.use_python_backend(lambda *a: outcome("wrong\n"))
        attempt = self.record(self.code, "print('wrong')")
        self.assertEqual(attempt.status, AttemptStatus.INCORRECT)
        self.assertEqual(list(attempt.mistakes.values_list("code", flat=True)), ["output_mismatch"])
        self.assertEqual(len(backend.requests), 1)


class AttemptNumberingTests(AttemptFixtures, TestCase):
    def test_numbers_are_sequential_per_enrollment_and_exercise(self) -> None:
        numbers = [self.record(self.mcq, "opt-a").attempt_number for _ in range(3)]
        self.assertEqual(numbers, [1, 2, 3])
        self.assertEqual(self.record(self.gap, "x").attempt_number, 1)
        self.assertEqual(self.record(self.numeric, "1").attempt_number, 1)

        other = make_user("other")
        other_profile = LearnerProfile.objects.create(user=other)
        Enrollment.objects.create(learner=other_profile, world=self.python_world)
        self.assertEqual(self.record(self.mcq, "opt-a", user=other).attempt_number, 1)
        self.assertEqual(self.record(self.mcq, SECRET_OPTION).attempt_number, 4)

    def test_number_conflicts_are_retried(self) -> None:
        real_store = services._store
        calls = []

        def flaky_store(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise IntegrityError("UNIQUE constraint failed (simulated race)")
            return real_store(*args, **kwargs)

        with mock.patch.object(services, "_store", side_effect=flaky_store):
            attempt = self.record(self.mcq, "opt-a")
        self.assertEqual(len(calls), 2)
        self.assertEqual(attempt.attempt_number, 1)

    def test_numbering_continues_after_existing_history(self) -> None:
        first = self.record(self.mcq, "opt-a")
        # Simulate a concurrent submission that already took number 2.
        ExerciseAttempt.objects.bulk_create(
            [
                ExerciseAttempt(
                    enrollment=self.enrollment,
                    exercise=self.mcq,
                    attempt_number=2,
                    status=AttemptStatus.INCORRECT,
                    score=0.0,
                    is_correct=False,
                    evaluator="multiple_choice",
                    message="m",
                )
            ]
        )
        self.assertEqual(first.attempt_number, 1)
        self.assertEqual(self.record(self.mcq, "opt-a").attempt_number, 3)


class AttemptAccessTests(AttemptFixtures, TestCase):
    def assert_denied(self, exercise, user) -> None:
        with self.assertRaises(PermissionDenied):
            record_attempt(user=user, exercise=exercise, answer=SECRET_OPTION)

    def test_anonymous_is_denied(self) -> None:
        self.assert_denied(self.mcq, AnonymousUser())
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_learner_without_enrollment_is_denied(self) -> None:
        stranger = make_user("stranger")
        self.assert_denied(self.mcq, stranger)
        LearnerProfile.objects.create(user=stranger)
        self.assert_denied(self.mcq, stranger)

    def test_paused_enrollment_is_denied_and_completed_allowed(self) -> None:
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status=EnrollmentStatus.PAUSED)
        self.assert_denied(self.mcq, self.user)
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status=EnrollmentStatus.COMPLETED)
        self.assertEqual(self.record(self.mcq, SECRET_OPTION).status, AttemptStatus.CORRECT)

    def test_other_world_is_denied(self) -> None:
        maths_only = make_user("mathsonly")
        profile = LearnerProfile.objects.create(user=maths_only)
        Enrollment.objects.create(learner=profile, world=self.maths_world)
        self.assert_denied(self.mcq, maths_only)
        self.assertEqual(self.record(self.numeric, "1", user=maths_only).status, "incorrect")

    def test_unpublished_exercises_are_denied(self) -> None:
        hidden = make_exercise(self.mcq.lesson, is_published=False)
        self.assert_denied(hidden, self.user)
        self.python_world.is_published = False
        self.python_world.save()
        self.assert_denied(self.mcq, self.user)
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_enrollment_is_resolved_from_the_user_and_exercise(self) -> None:
        other = make_user("other")
        other_profile = LearnerProfile.objects.create(user=other)
        other_enrollment = Enrollment.objects.create(learner=other_profile, world=self.python_world)
        attempt = self.record(self.mcq, "opt-a")
        self.assertEqual(attempt.enrollment, self.enrollment)
        self.assertNotEqual(attempt.enrollment, other_enrollment)
        self.assertEqual(resolve_enrollment(other, self.mcq), other_enrollment)
        self.assertEqual(resolve_enrollment(self.user, self.numeric), self.maths_enrollment)
        with self.assertRaises(TypeError):
            record_attempt(
                user=self.user, exercise=self.mcq, answer="opt-a", enrollment=other_enrollment
            )

    def test_unrelated_world_exercise_resolves_nothing(self) -> None:
        lonely = make_exercise(make_lesson_chain("Unenrolled World"))
        self.assert_denied(lonely, self.user)


class AttemptInputValidationTests(AttemptFixtures, TestCase):
    def test_bad_inputs_create_nothing(self) -> None:
        for kwargs, field in (
            ({"hint_level": -1}, "hint_level"),
            ({"hint_level": 11}, "hint_level"),
            ({"hint_level": True}, "hint_level"),
            ({"hint_level": "1"}, "hint_level"),
            ({"hint_level": 1.5}, "hint_level"),
            ({"used_explanation": 1}, "used_explanation"),
            ({"used_solution": "yes"}, "used_solution"),
            ({"duration_seconds": -5}, "duration_seconds"),
            ({"duration_seconds": 86_401}, "duration_seconds"),
            ({"duration_seconds": 12.5}, "duration_seconds"),
            ({"duration_seconds": False}, "duration_seconds"),
            ({"answer": object()}, "answer"),
            ({"answer": float("nan")}, "answer"),
            ({"answer": {1, 2}}, "answer"),
            ({"answer": "x" * 100_001}, "answer"),
        ):
            with self.subTest(**{k: str(v)[:20] for k, v in kwargs.items()}):
                call = {"user": self.user, "exercise": self.mcq, "answer": "opt-a", **kwargs}
                with self.assertRaises(AttemptInputError) as ctx:
                    record_attempt(**call)
                self.assertIn(field, ctx.exception.message_dict)
        self.assertFalse(ExerciseAttempt.objects.exists())
        self.assertFalse(AttemptMistake.objects.exists())

    def test_boundary_inputs_are_accepted(self) -> None:
        attempt = self.record(self.mcq, "opt-a", hint_level=10, duration_seconds=86_400)
        self.assertEqual((attempt.hint_level, attempt.duration_seconds), (10, 86_400))
        attempt = self.record(self.mcq, "opt-a", hint_level=0, duration_seconds=0)
        self.assertEqual(attempt.duration_seconds, 0)

    def test_answers_of_any_shape_reach_the_evaluator(self) -> None:
        for answer in (None, 12, ["opt-a"], {"id": "opt-a"}, True):
            with self.subTest(answer=answer):
                attempt = self.record(self.mcq, answer)
                self.assertEqual(attempt.status, AttemptStatus.INVALID)
                self.assertEqual(
                    ExerciseAttempt.objects.get(pk=attempt.pk).submitted_answer, answer
                )

    def test_gap_answer_is_stored_as_submitted(self) -> None:
        attempt = self.record(self.gap, f"  {SECRET_GAP}  ")
        self.assertEqual(attempt.status, AttemptStatus.CORRECT)
        self.assertEqual(attempt.submitted_answer, f"  {SECRET_GAP}  ")
