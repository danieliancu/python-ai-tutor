"""AI help feeds the next attempt's assistance record, and attempts reset it."""

from unittest import mock

from django.test import TestCase

from apps.ai_tutor.models import TutorExerciseState
from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.attempts.models import ExerciseAttempt
from apps.attempts.tests.helpers import SECRET_GAP
from apps.learner_intelligence.models import ConceptState
from apps.learner_intelligence.scoring import Evidence, assistance_factor


def assistance(attempt) -> tuple:
    return (attempt.hint_level, attempt.used_explanation, attempt.used_solution)


class AttemptIntegrationTests(TutorFixtures, TestCase):
    def test_tutor_help_cannot_be_hidden_by_the_client(self) -> None:
        self.tutor("hint", exercise=self.gap)
        self.tutor("explain", exercise=self.gap)  # strong hint
        self.tutor("explain", exercise=self.gap)  # explanation
        attempt = self.record(
            self.gap, "wrong", hint_level=0, used_explanation=False, used_solution=False
        )
        self.assertEqual(assistance(attempt), (2, True, False))
        attempt.refresh_from_db()
        self.assertEqual(assistance(attempt), (2, True, False))

    def test_solution_discounts_the_evidence(self) -> None:
        for _ in range(4):
            self.tutor("solution", exercise=self.gap)
        attempt = self.record(self.gap, SECRET_GAP)
        self.assertEqual(attempt.status, "correct")
        self.assertEqual(assistance(attempt), (2, True, True))
        self.assertLess(assistance_factor(Evidence.from_attempt(attempt)), 0.25)
        state = ConceptState.objects.get(enrollment=self.enrollment, concept=self.concept)
        self.assertLess(float(state.independence_score), 25)

    def test_attempts_reset_the_record(self) -> None:
        self.tutor("hint", exercise=self.gap)
        self.tutor("hint", exercise=self.gap)
        self.tutor("explain", exercise=self.gap)
        first = self.record(self.gap, "wrong")
        self.assertEqual(assistance(first), (2, True, False))
        row = TutorExerciseState.objects.get(enrollment=self.enrollment, exercise=self.gap)
        self.assertEqual(
            (row.hint_level, row.used_explanation, row.last_attempt), (0, False, first)
        )

        second = self.record(self.gap, "still wrong")
        self.assertEqual(assistance(second), (0, False, False))

        # Help after an attempt counts towards the next one, and the ladder starts over.
        outcome = self.tutor("hint", exercise=self.gap)
        self.assertEqual(outcome.turn.response_kind, "hint")
        self.assertEqual(outcome.turn.attempt, second)
        third = self.record(self.gap, "wrong again")
        self.assertEqual(assistance(third), (1, False, False))

    def test_client_can_report_more_help(self) -> None:
        self.tutor("hint", exercise=self.gap)
        attempt = self.record(self.gap, "wrong", hint_level=2, used_solution=True)
        self.assertEqual(assistance(attempt), (2, False, True))

    def test_help_is_per_exercise_and_enrollment(self) -> None:
        self.tutor("solution", exercise=self.mcq)
        attempt = self.record(self.gap, "wrong")
        self.assertEqual(assistance(attempt), (0, False, False))

    def test_reset_failure_keeps_the_attempt(self) -> None:
        self.tutor("hint", exercise=self.gap)
        with (
            mock.patch(
                "apps.ai_tutor.assistance.record_attempt_boundary",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR") as logs,
        ):
            attempt = self.record(self.gap, "wrong")
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertEqual(assistance(attempt), (1, False, False))
        self.assertTrue(ConceptState.objects.filter(enrollment=self.enrollment).exists())
        self.assertIn("Tutor assistance refresh failed", logs.output[0])
        self.assertNotIn("wrong", logs.output[0])
        # Not reset: the help is (temporarily) over-counted, never lost.
        row = TutorExerciseState.objects.get(enrollment=self.enrollment, exercise=self.gap)
        self.assertEqual(row.hint_level, 1)

    def test_unreadable_tutor_record_keeps_client_values(self) -> None:
        with (
            mock.patch(
                "apps.ai_tutor.assistance.merge_with_client", side_effect=RuntimeError("down")
            ),
            self.assertLogs("apps.attempts.services", "ERROR"),
        ):
            attempt = self.record(self.gap, "wrong", hint_level=1)
        self.assertEqual(assistance(attempt), (1, False, False))

    def test_submitting_never_calls_the_provider(self) -> None:
        with mock.patch("apps.ai_tutor.services.get_provider") as factory:
            self.record(self.gap, "wrong")
        factory.assert_not_called()
        self.assertEqual(self.provider.requests, [])
