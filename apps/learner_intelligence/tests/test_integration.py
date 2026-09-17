from decimal import Decimal
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.attempts.tests.helpers import SECRET_OPTION
from apps.learner_intelligence.models import ConceptState
from apps.learner_intelligence.tests.helpers import IntelligenceFixtures


class AttemptIntegrationTests(IntelligenceFixtures, TestCase):
    def state(self) -> ConceptState:
        return ConceptState.objects.get(enrollment=self.enrollment, concept=self.concept)

    def test_recording_an_attempt_refreshes_state(self) -> None:
        attempt = self.record(self.mcq, SECRET_OPTION, duration_seconds=20)
        self.assertEqual(attempt.status, AttemptStatus.CORRECT)
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        state = self.state()
        self.assertEqual(state.evidence_count, 1)
        self.assertEqual(state.mastery_score, Decimal("60.00"))  # one answer: 0.6 confidence
        self.assertEqual(state.mode_states.get().learning_mode, "recognise")

        self.record(self.mcq, "opt-a")
        state = self.state()
        self.assertEqual((state.evidence_count, state.correct_count), (2, 1))
        self.assertEqual(state.last_attempt_at, ExerciseAttempt.objects.latest("id").submitted_at)

    def test_unavailable_attempts_are_tracked_without_judgement(self) -> None:
        self.break_python_runner()
        attempt = self.record(self.code, "print('hi')")
        self.assertEqual(attempt.status, AttemptStatus.UNAVAILABLE)
        state = self.state()
        self.assertEqual(state.mastery_band, "not_started")
        self.assertEqual(state.last_attempt_at, attempt.submitted_at)

    def test_refresh_failure_keeps_the_attempt(self) -> None:
        with (
            mock.patch(
                "apps.learner_intelligence.services.refresh_for_attempt",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR") as logs,
        ):
            attempt = self.record(self.mcq, SECRET_OPTION)
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertFalse(ConceptState.objects.exists())
        self.assertIn("rebuild_learner_intelligence", logs.output[0])

    def test_database_failure_during_refresh_keeps_the_attempt(self) -> None:
        with (
            mock.patch(
                "apps.learner_intelligence.services.ConceptState.objects.create",
                side_effect=DatabaseError("disk full"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR"),
        ):
            attempt = self.record(self.mcq, SECRET_OPTION)
        # The outer connection is still usable and the attempt is stored.
        self.assertEqual(ExerciseAttempt.objects.get(pk=attempt.pk).status, "correct")
        self.assertFalse(ConceptState.objects.exists())
        # A later refresh (or rebuild) recovers the state.
        self.record(self.mcq, SECRET_OPTION)
        self.assertEqual(self.state().evidence_count, 2)
