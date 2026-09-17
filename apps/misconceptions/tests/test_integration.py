from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from apps.attempts.models import ExerciseAttempt
from apps.learner_intelligence.models import ConceptState
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.tests.helpers import MisconceptionFixtures


class RecordAttemptIntegrationTests(MisconceptionFixtures, TestCase):
    def test_recording_attempts_refreshes_misconceptions(self) -> None:
        first = self.record(self.range_gap, "5")
        self.assertEqual(first.status, "incorrect")
        self.assertEqual(self.state("range-exclusive-stop").status, "watch")
        self.record(self.range_gap, "5")
        self.assertEqual(self.state("range-exclusive-stop").status, "active")
        self.assertTrue(ConceptState.objects.filter(enrollment=self.enrollment).exists())

        self.record(self.range_gap, "6")
        self.assertTrue(
            MisconceptionEvidence.objects.filter(kind="counter", code="off-by-one").exists()
        )

    def test_misconception_failure_keeps_attempt_and_intelligence(self) -> None:
        with (
            mock.patch(
                "apps.misconceptions.services.refresh_for_attempt",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR") as logs,
        ):
            attempt = self.record(self.range_gap, "5")
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        state = ConceptState.objects.get(enrollment=self.enrollment, concept=self.concept)
        self.assertEqual(state.evidence_count, 1)
        self.assertFalse(MisconceptionState.objects.exists())
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Misconception refresh failed", logs.output[0])
        self.assertIn("rebuild_misconceptions", logs.output[0])
        self.assertNotIn("'5'", logs.output[0])

    def test_database_failure_is_rolled_back_in_isolation(self) -> None:
        with (
            mock.patch(
                "apps.misconceptions.services.MisconceptionState.objects.create",
                side_effect=DatabaseError("disk full"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR"),
        ):
            attempt = self.record(self.range_gap, "5")
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(ConceptState.objects.filter(enrollment=self.enrollment).exists())
        # The half-written evidence was rolled back with the failed misconception refresh.
        self.assertFalse(MisconceptionEvidence.objects.exists())
        # The next attempt (or a rebuild) recovers everything.
        self.record(self.range_gap, "5")
        self.assertEqual(self.state("off-by-one").status, "active")

    def test_intelligence_failure_does_not_block_misconceptions(self) -> None:
        with (
            mock.patch(
                "apps.learner_intelligence.services.refresh_for_attempt",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.attempts.services", "ERROR"),
        ):
            self.record(self.range_gap, "5")
        self.assertFalse(ConceptState.objects.exists())
        self.assertTrue(MisconceptionState.objects.exists())

    def test_failing_detector_is_logged_safely_and_skipped(self) -> None:
        with (
            mock.patch(
                "apps.misconceptions.domains.python.detectors.FillGapOffByOneDetector.check",
                side_effect=ValueError("print('SECRET')"),
            ),
            self.assertLogs("apps.misconceptions.services", "ERROR") as logs,
        ):
            self.record(self.range_gap, "5")
        self.assertIn("python_fill_gap_off_by_one", logs.output[0])
        self.assertIn("ValueError", logs.output[0])
        self.assertNotIn("SECRET", logs.output[0])
        # The generic candidate evidence is still recorded.
        self.assertEqual(self.state("off-by-one").status, "watch")
