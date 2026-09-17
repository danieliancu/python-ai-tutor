from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.ai_tutor.assistance import (
    authoritative_for_attempt,
    reconcile_assistance_state,
    reconstruct_assistance,
    record_attempt_boundary,
)
from apps.ai_tutor.models import TutorExerciseState
from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.ai_tutor.types import AssistanceState
from apps.attempts.exceptions import AttemptTutorTurnInProgress
from apps.attempts.models import ExerciseAttempt


class AssistanceTests(TutorFixtures, TestCase):
    def delivered(self, kind, exercise=None, *, minutes_ago=10, status="complete", **fields):
        """A tutor turn that finished ``minutes_ago`` minutes ago."""
        when = timezone.now() - timedelta(minutes=minutes_ago)
        turn = self.old_turn(
            exercise=exercise or self.gap,
            status=status,
            response_kind=kind,
            requested_intent="hint",
            seconds_ago=minutes_ago * 60 + 1,
            **fields,
        )
        turn.completed_at = when if status != "pending" else None
        turn.save()
        return turn

    def attempt_at(self, exercise, minutes_ago):
        attempt = self.make_attempt(exercise)
        ExerciseAttempt.objects.filter(pk=attempt.pk).update(
            submitted_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        attempt.refresh_from_db()
        return attempt

    def test_nothing_recorded_means_no_help(self) -> None:
        self.assertEqual(reconstruct_assistance(self.enrollment, self.mcq), AssistanceState())

    def test_reconstruction_replays_completed_turns(self) -> None:
        self.delivered("hint", minutes_ago=30)
        self.delivered("strong_hint", minutes_ago=20)
        self.delivered("explanation", minutes_ago=10)
        self.delivered("guidance", minutes_ago=9)
        self.delivered("solution", minutes_ago=8, status="failed")
        self.assertFalse(TutorExerciseState.objects.exists())
        state = reconcile_assistance_state(self.enrollment, self.gap)
        self.assertEqual(state, AssistanceState(2, True, False))
        row = TutorExerciseState.objects.get()
        self.assertEqual(
            (row.hint_level, row.used_explanation, row.used_solution), (2, True, False)
        )
        # Idempotent.
        updated_at = row.updated_at
        self.assertEqual(reconcile_assistance_state(self.enrollment, self.gap), state)
        row.refresh_from_db()
        self.assertEqual(row.updated_at, updated_at)
        # Other learners and exercises are unaffected.
        self.assertEqual(
            reconstruct_assistance(self.english_enrollment, self.gap), AssistanceState()
        )
        self.assertEqual(reconstruct_assistance(self.enrollment, self.mcq), AssistanceState())

    def test_attempt_boundary(self) -> None:
        self.delivered("hint", minutes_ago=40)
        self.delivered("explanation", minutes_ago=30)
        boundary = self.attempt_at(self.gap, 20)
        self.delivered("hint", minutes_ago=10)
        self.assertEqual(
            reconstruct_assistance(self.enrollment, self.gap), AssistanceState(1, False, False)
        )
        reconcile_assistance_state(self.enrollment, self.gap)
        self.assertEqual(TutorExerciseState.objects.get().last_attempt, boundary)

    def test_stale_cache_is_repaired(self) -> None:
        TutorExerciseState.objects.create(
            enrollment=self.enrollment, exercise=self.gap, hint_level=2, used_solution=True
        )
        self.assertEqual(reconcile_assistance_state(self.enrollment, self.gap), AssistanceState())
        row = TutorExerciseState.objects.get()
        self.assertEqual((row.hint_level, row.used_solution), (0, False))

    def test_attempt_boundary_resets_the_cache(self) -> None:
        self.delivered("strong_hint", minutes_ago=5)
        self.delivered("solution", minutes_ago=4)
        attempt = self.make_attempt(self.gap)
        record_attempt_boundary(attempt)
        row = TutorExerciseState.objects.get(enrollment=self.enrollment, exercise=self.gap)
        self.assertEqual(
            (row.hint_level, row.used_explanation, row.used_solution, row.last_attempt),
            (0, False, False, attempt),
        )

    def test_authoritative_merge_uses_max_and_or(self) -> None:
        self.delivered("hint", minutes_ago=5)
        self.delivered("explanation", minutes_ago=4)
        client = {"hint_level": 0, "used_explanation": False, "used_solution": False}
        self.assertEqual(
            authoritative_for_attempt(self.enrollment, self.gap, **client),
            {"hint_level": 1, "used_explanation": True, "used_solution": False},
        )
        # The client may report more help than the tutor gave.
        self.assertEqual(
            authoritative_for_attempt(
                self.enrollment, self.gap, hint_level=2, used_explanation=False, used_solution=True
            ),
            {"hint_level": 2, "used_explanation": True, "used_solution": True},
        )

    def test_pending_turn_blocks_attempt_assistance(self) -> None:
        self.delivered("hint", status="pending", minutes_ago=0)
        client = {"hint_level": 0, "used_explanation": False, "used_solution": False}
        with self.assertRaises(AttemptTutorTurnInProgress):
            authoritative_for_attempt(self.enrollment, self.gap, **client)
        # Other exercises are not blocked.
        authoritative_for_attempt(self.enrollment, self.mcq, **client)
        # A stale pending turn no longer blocks, and is closed.
        later = timezone.now() + timedelta(minutes=10)
        self.assertEqual(
            authoritative_for_attempt(self.enrollment, self.gap, now=later, **client), client
        )
