"""AI help feeds the next attempt's assistance record, and attempts reset it."""

import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.attempts.exceptions import AttemptAssistanceUnavailable, AttemptTutorTurnInProgress
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

    def test_unreadable_server_assistance_fails_closed(self) -> None:
        for _ in range(4):
            self.tutor("solution", exercise=self.gap)
        with (
            mock.patch(
                "apps.ai_tutor.assistance.reconstruct_assistance",
                side_effect=RuntimeError("database hiccup"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR") as logs,
            self.assertRaises(AttemptAssistanceUnavailable),
        ):
            self.record(self.gap, SECRET_GAP, used_solution=False)
        self.assertFalse(ExerciseAttempt.objects.exists())
        self.assertNotIn(SECRET_GAP, " ".join(logs.output))
        # Once the state is readable again, the attempt records the solution help.
        attempt = self.record(self.gap, SECRET_GAP, used_solution=False)
        self.assertTrue(attempt.used_solution)

    def test_reset_failure_is_recovered_from_history(self) -> None:
        for _ in range(4):
            self.tutor("solution", exercise=self.gap)
        with (
            mock.patch(
                "apps.ai_tutor.assistance.record_attempt_boundary",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR"),
        ):
            first = self.record(self.gap, "wrong")
        self.assertTrue(first.used_solution)
        stale = TutorExerciseState.objects.get(enrollment=self.enrollment, exercise=self.gap)
        self.assertTrue(stale.used_solution)  # the cache was not reset...
        second = self.record(self.gap, "still wrong")
        # ...but the next attempt is built from history, so the old solution doesn't leak.
        self.assertEqual(assistance(second), (0, False, False))
        # And the ladder starts over for the tutor as well.
        self.assertEqual(self.tutor("solution", exercise=self.gap).turn.response_kind, "hint")

    def test_pending_tutor_turn_blocks_submission(self) -> None:
        self.old_turn(exercise=self.gap, status="pending", response_kind="hint", seconds_ago=1)
        with self.assertRaises(AttemptTutorTurnInProgress):
            self.record(self.gap, "wrong")
        self.assertFalse(ExerciseAttempt.objects.exists())
        TutorTurn.objects.update(status="failed", error_code="provider_timeout")
        self.assertEqual(self.record(self.gap, "wrong").status, "incorrect")

    def test_attempts_work_with_the_tutor_disabled(self) -> None:
        with override_settings(AI_TUTOR={"ENABLED": False}):
            attempt = self.record(self.gap, "wrong", hint_level=1)
        self.assertEqual(assistance(attempt), (1, False, False))

    def test_views_report_temporary_blocks(self) -> None:
        self.client.force_login(self.user)
        url = reverse("attempts:exercise_attempts", args=[self.gap.pk])
        pending = self.old_turn(
            exercise=self.gap, status="pending", response_kind="hint", seconds_ago=1
        )
        response = self.client.post(
            url, data=json.dumps({"answer": "x"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "tutor_turn_in_progress")
        pending.delete()
        with mock.patch(
            "apps.ai_tutor.assistance.reconstruct_assistance", side_effect=RuntimeError("x")
        ):
            response = self.client.post(
                url, data=json.dumps({"answer": "x"}), content_type="application/json"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "error": "assistance_unavailable",
                "message": "Your answer could not be recorded safely right now. Please try again.",
            },
        )
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_submitting_never_calls_the_provider(self) -> None:
        with mock.patch("apps.ai_tutor.services.get_provider") as factory:
            self.record(self.gap, "wrong")
        factory.assert_not_called()
        self.assertEqual(self.provider.requests, [])
