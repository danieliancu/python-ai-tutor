"""Phase 8 hardening: serialized exercise turns and reconstructable assistance."""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.providers.base import TutorTimeout
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.services import TutorRequestError
from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.ai_tutor.types import AssistanceState


class ReentrantProvider(FakeTutorProvider):
    """While generating, asks for more help on the same exercise (a simulated race)."""

    def __init__(self, test, **kwargs):
        super().__init__(**kwargs)
        self.test = test
        self.inner_error = None

    def generate(self, request):
        pending = TutorTurn.objects.get(status="pending")
        self.test.assertEqual(pending.response_kind, request.response_kind)
        self.test.assertIsNone(pending.completed_at)
        inner = FakeTutorProvider()
        try:
            self.test.tutor("hint", exercise=self.test.gap, provider=inner)
        except TutorRequestError as exc:
            self.inner_error = exc
        self.test.assertEqual(inner.requests, [])
        return super().generate(request)


class ReservationTests(TutorFixtures, TestCase):
    def pending(self, exercise=None, seconds_ago=1, **fields):
        return self.old_turn(
            exercise=exercise if exercise is not None else self.gap,
            status="pending",
            response_kind="hint",
            seconds_ago=seconds_ago,
            **fields,
        )

    def test_database_allows_one_pending_turn_per_exercise(self) -> None:
        self.pending()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.pending()
        self.pending(exercise=self.mcq)
        self.old_turn(status="pending", requested_intent="next_step", response_kind="next_step")
        self.old_turn(status="pending", requested_intent="next_step", response_kind="next_step")
        self.pending(enrollment=self.english_enrollment)
        self.old_turn(exercise=self.gap, status="complete", response_kind="hint")
        self.old_turn(exercise=self.gap, status="failed", response_kind="")

    def test_concurrent_request_is_rejected_without_calling_the_provider(self) -> None:
        first = self.pending()
        with self.assertRaises(TutorRequestError) as caught:
            self.tutor("hint", exercise=self.gap)
        self.assertEqual(
            (caught.exception.code, caught.exception.status), ("tutor_turn_in_progress", 409)
        )
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(TutorTurn.objects.count(), 1)

        # The first request completes at hint level: the next request advances the ladder.
        first.status = "complete"
        first.completed_at = timezone.now()
        first.save()
        self.assertEqual(self.tutor("hint", exercise=self.gap).turn.response_kind, "strong_hint")

    def test_failed_turn_releases_the_exercise(self) -> None:
        first = self.pending()
        first.status = "failed"
        first.completed_at = timezone.now()
        first.save()
        self.assertEqual(self.tutor("hint", exercise=self.gap).turn.response_kind, "hint")

    def test_simultaneous_requests_cannot_both_progress(self) -> None:
        provider = ReentrantProvider(self)
        outcome = self.tutor("hint", exercise=self.gap, provider=provider)
        self.assertEqual(outcome.turn.response_kind, "hint")
        self.assertEqual(provider.inner_error.code, "tutor_turn_in_progress")
        self.assertEqual(provider.inner_error.status, 409)
        self.assertEqual(TutorTurn.objects.count(), 1)
        self.assertEqual(self.tutor("hint", exercise=self.gap).turn.response_kind, "strong_hint")

    def test_other_exercises_and_turns_without_exercise_are_not_blocked(self) -> None:
        self.pending()
        self.assertEqual(self.tutor("hint", exercise=self.mcq).turn.status, "complete")
        self.assertEqual(self.tutor("next_step").turn.status, "complete")
        self.assertEqual(self.tutor("ask", "general question").turn.status, "complete")

    def test_stale_pending_turn_is_recovered(self) -> None:
        stale = self.pending(seconds_ago=121)
        outcome = self.tutor("hint", exercise=self.gap)
        self.assertEqual(outcome.turn.status, "complete")
        stale.refresh_from_db()
        self.assertEqual((stale.status, stale.error_code), ("failed", "stale_pending_turn"))
        self.assertIsNotNone(stale.completed_at)

    def test_fresh_pending_turn_is_not_stale(self) -> None:
        fresh = self.pending(seconds_ago=60)
        with self.assertRaises(TutorRequestError):
            self.tutor("hint", exercise=self.gap)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, "pending")

    def test_failure_releases_the_reservation(self) -> None:
        with self.assertRaises(TutorRequestError):
            self.tutor("hint", exercise=self.gap, provider=FakeTutorProvider(error=TutorTimeout()))
        failed = TutorTurn.objects.get()
        self.assertEqual((failed.status, failed.error_code), ("failed", "provider_timeout"))
        self.assertEqual(failed.response_kind, "hint")
        self.assertIsNotNone(failed.completed_at)
        self.assertEqual(self.tutor("hint", exercise=self.gap).turn.response_kind, "hint")

    def test_completion_and_assistance_commit_together(self) -> None:
        with (
            mock.patch(
                "apps.ai_tutor.services.assistance.reconcile_assistance_state",
                side_effect=[AssistanceState(), RuntimeError("cache down")],
            ),
            self.assertRaises(RuntimeError),
        ):
            self.tutor("hint", exercise=self.gap)
        turn = TutorTurn.objects.get()
        # The completion was rolled back with the failed assistance update.
        self.assertEqual((turn.status, turn.error_code), ("failed", "internal_error"))
        self.assertEqual(turn.assistant_message, "")
        self.assertEqual(self.tutor("hint", exercise=self.gap).turn.response_kind, "hint")

    def test_context_failure_releases_the_reservation(self) -> None:
        with (
            mock.patch(
                "apps.ai_tutor.services.build_tutor_context", side_effect=RuntimeError("bug")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.tutor("hint", exercise=self.gap)
        self.assertEqual(TutorTurn.objects.get().status, "failed")
        self.assertEqual(self.provider.requests, [])

    def test_completed_at_is_set(self) -> None:
        outcome = self.tutor("hint", exercise=self.gap)
        self.assertIsNotNone(outcome.turn.completed_at)
        self.assertGreaterEqual(outcome.turn.completed_at, outcome.turn.created_at)
        self.assertIsNotNone(self.tutor("next_step").turn.completed_at)

    def test_view_returns_409(self) -> None:
        self.client.force_login(self.user)
        self.pending()
        with mock.patch("apps.ai_tutor.services.get_provider", return_value=self.provider):
            response = self.client.post(
                f"/app/worlds/{self.python_world.pk}/tutor/turns/",
                data={"intent": "hint", "exercise_id": self.gap.pk},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {
                "error": "tutor_turn_in_progress",
                "message": "A tutor response for this exercise is already being generated.",
            },
        )
        self.assertEqual(self.provider.requests, [])


class RebuildCommandTests(TutorFixtures, TestCase):
    def test_rebuild_is_idempotent(self) -> None:
        self.tutor("hint", exercise=self.gap)
        self.tutor("explain", exercise=self.gap)
        self.tutor("hint", exercise=self.mcq, enrollment=self.enrollment)
        TutorExerciseState.objects.all().delete()
        TutorExerciseState.objects.create(
            enrollment=self.english_enrollment, exercise=self.translation, used_solution=True
        )
        out = StringIO()
        call_command("rebuild_tutor_assistance", stdout=out)
        self.assertIn("2 created, 1 updated, 0 unchanged (3 total)", out.getvalue())
        row = TutorExerciseState.objects.get(exercise=self.gap)
        self.assertEqual((row.hint_level, row.used_explanation), (2, False))
        self.assertFalse(TutorExerciseState.objects.get(exercise=self.translation).used_solution)

        out = StringIO()
        call_command("rebuild_tutor_assistance", stdout=out)
        self.assertIn("0 created, 0 updated, 3 unchanged (3 total)", out.getvalue())

        out = StringIO()
        call_command(
            "rebuild_tutor_assistance",
            "--enrollment-id",
            str(self.english_enrollment.pk),
            stdout=out,
        )
        self.assertIn("(1 total)", out.getvalue())
        with self.assertRaises(CommandError):
            call_command("rebuild_tutor_assistance", "--enrollment-id", "999999", stdout=out)

    def test_old_turn_timestamps(self) -> None:
        # Sanity: the stale threshold honours the provider timeout.
        from apps.ai_tutor.assistance import stale_after

        self.assertEqual(stale_after(), timedelta(seconds=120))
