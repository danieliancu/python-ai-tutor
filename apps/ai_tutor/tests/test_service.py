from unittest import mock

from django.forms.models import model_to_dict
from django.test import TestCase, override_settings

from apps.ai_tutor.constants import TUTOR_PROMPT_VERSION
from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.providers.base import (
    TutorInvalidResponse,
    TutorRateLimited,
    TutorTimeout,
    TutorUnavailable,
)
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.services import TutorRequestError
from apps.ai_tutor.tests.helpers import ENABLED, TutorFixtures
from apps.ai_tutor.types import AssistanceState
from apps.curriculum.tests.helpers import make_world
from apps.exercises.models import Exercise
from apps.learner_intelligence.models import ConceptState
from apps.learners.models import Enrollment
from apps.misconceptions.models import MisconceptionState
from apps.next_action.engine import next_action_for_enrollment


class TutorServiceTests(TutorFixtures, TestCase):
    def assertRequestError(self, code, status, **kwargs):
        with self.assertRaises(TutorRequestError) as caught:
            self.tutor(**kwargs)
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))

    def state(self, exercise=None):
        row = TutorExerciseState.objects.filter(
            enrollment=self.enrollment, exercise=exercise or self.mcq
        ).first()
        return None if row is None else (row.hint_level, row.used_explanation, row.used_solution)

    def test_ask_creates_a_completed_turn_without_escalation(self) -> None:
        outcome = self.tutor("ask", "What does this concept mean?", self.mcq)
        turn = TutorTurn.objects.get()
        self.assertEqual(outcome.turn, turn)
        self.assertEqual(
            (turn.status, turn.requested_intent, turn.response_kind),
            ("complete", "ask", "guidance"),
        )
        self.assertEqual(turn.user_message, "What does this concept mean?")
        self.assertEqual(turn.assistant_message, "Let's look at this together. (guidance)")
        self.assertEqual((turn.provider, turn.model), ("fake", "fake-model"))
        self.assertEqual((turn.input_tokens, turn.output_tokens), (120, 30))
        self.assertEqual(turn.prompt_version, TUTOR_PROMPT_VERSION)
        self.assertIsNotNone(turn.latency_ms)
        self.assertEqual(turn.provider_response_id, "fake-response")
        self.assertEqual(turn.exercise, self.mcq)
        self.assertIsNone(turn.attempt)
        self.assertFalse(turn.should_retry)
        self.assertEqual(outcome.assistance, AssistanceState())
        self.assertEqual(self.state(), (0, False, False))

    def test_hint_ladder(self) -> None:
        kinds = [self.tutor("hint", exercise=self.mcq).turn.response_kind for _ in range(3)]
        self.assertEqual(kinds, ["hint", "strong_hint", "strong_hint"])
        self.assertEqual(self.state(), (2, False, False))

    def test_solution_escalation(self) -> None:
        results = [self.tutor("solution", "Just give me the answer.", self.mcq) for _ in range(4)]
        self.assertEqual(
            [r.turn.response_kind for r in results],
            ["hint", "strong_hint", "explanation", "solution"],
        )
        self.assertEqual(results[-1].assistance, AssistanceState(2, True, True))
        self.assertEqual(self.state(), (2, True, True))
        self.assertTrue(self.provider.requests[-1].solution_allowed)
        self.assertFalse(self.provider.requests[-2].solution_allowed)

    def test_explanation_escalation(self) -> None:
        kinds = [self.tutor("explain", exercise=self.mcq).turn.response_kind for _ in range(3)]
        self.assertEqual(kinds, ["hint", "strong_hint", "explanation"])
        self.assertEqual(self.state(), (2, True, False))

    def test_provider_cannot_escalate(self) -> None:
        cheeky = FakeTutorProvider(kind="solution")
        self.assertRequestError(
            "tutor_unavailable", 503, intent="hint", exercise=self.mcq, provider=cheeky
        )
        turn = TutorTurn.objects.get()
        self.assertEqual((turn.status, turn.error_code), ("failed", "provider_invalid_response"))
        self.assertEqual(turn.assistant_message, "")
        self.assertIsNotNone(turn.completed_at)
        self.assertEqual(self.state(), (0, False, False))

    def test_provider_failures_change_nothing(self) -> None:
        self.record(self.mcq, "opt-a")
        before = {
            "concept": [model_to_dict(s) for s in ConceptState.objects.all()],
            "misconceptions": list(MisconceptionState.objects.values()),
            "tutor": list(TutorExerciseState.objects.values()),
            "next": next_action_for_enrollment(self.enrollment),
        }
        for error, code, status in (
            (TutorTimeout(), "provider_timeout", 503),
            (TutorUnavailable(), "provider_unavailable", 503),
            (TutorInvalidResponse(), "provider_invalid_response", 503),
            (TutorRateLimited(), "provider_rate_limited", 429),
        ):
            with self.subTest(code=code):
                failing = FakeTutorProvider(error=error)
                expected = "tutor_rate_limited" if status == 429 else "tutor_unavailable"
                self.assertRequestError(
                    expected, status, intent="hint", exercise=self.mcq, provider=failing
                )
                turn = TutorTurn.objects.latest("id")
                self.assertEqual((turn.status, turn.error_code), ("failed", code))
        after = {
            "concept": [model_to_dict(s) for s in ConceptState.objects.all()],
            "misconceptions": list(MisconceptionState.objects.values()),
            "tutor": list(TutorExerciseState.objects.values()),
            "next": next_action_for_enrollment(self.enrollment, now=before["next"].generated_at),
        }
        self.assertEqual(before, after)
        self.assertEqual(self.state(), (0, False, False))

    def test_disabled_or_unconfigured_tutor_never_calls_a_provider(self) -> None:
        for settings in (
            {**ENABLED, "ENABLED": False},
            {**ENABLED, "OPENAI_API_KEY": ""},
        ):
            with (
                self.subTest(settings=settings),
                override_settings(AI_TUTOR=settings),
                mock.patch("apps.ai_tutor.services.get_provider") as factory,
            ):
                self.assertRequestError("tutor_unavailable", 503, provider=None, message="hi")
                factory.assert_not_called()
        self.assertFalse(TutorTurn.objects.exists())

    def test_input_validation(self) -> None:
        self.assertRequestError("invalid_intent", 400, intent="grade_me")
        self.assertRequestError("message_required", 400, intent="ask", message="   ")
        self.assertRequestError("invalid_message", 400, intent="ask", message=42)
        self.assertRequestError("message_too_long", 400, intent="ask", message="x" * 4001)
        self.tutor("ask", "x" * 4000)
        self.tutor("hint", "", self.mcq)
        with override_settings(AI_TUTOR={**ENABLED, "MAX_USER_CHARS": "10"}):
            self.assertRequestError("message_too_long", 400, intent="hint", message="x" * 11)

    def test_rate_limit(self) -> None:
        for _ in range(19):
            self.old_turn(seconds_ago=30)
        self.old_turn(seconds_ago=61)
        self.tutor("ask", "one more")  # the 20th within the minute
        self.assertRequestError("rate_limited", 429, intent="ask", message="too many")
        self.assertEqual(TutorTurn.objects.count(), 21)
        # Another enrollment has its own allowance.
        other = self.tutor("ask", "hello", enrollment=self.english_enrollment)
        self.assertEqual(other.turn.status, "complete")

    def test_exercise_must_belong_to_the_world(self) -> None:
        self.assertRequestError("forbidden", 403, intent="hint", exercise=self.translation)
        Exercise.objects.filter(pk=self.gap.pk).update(is_published=False)
        self.assertRequestError("forbidden", 403, intent="hint", exercise=self.gap)
        with self.assertRaises(TutorRequestError):
            self.tutor("ask", "hi", exercise=Exercise(pk=999_999))

    def test_help_without_exercise_uses_the_next_action(self) -> None:
        decision = next_action_for_enrollment(self.enrollment)
        outcome = self.tutor("hint")
        self.assertEqual(outcome.turn.exercise_id, decision.exercise_id)
        self.assertEqual(outcome.turn.response_kind, "hint")

    def test_help_needs_an_exercise_context(self) -> None:
        empty = Enrollment.objects.create(learner=self.profile, world=make_world("Empty"))
        for intent in ("hint", "explain", "solution"):
            with self.subTest(intent=intent), self.assertRaises(TutorRequestError) as caught:
                self.tutor(intent, enrollment=empty)
            self.assertEqual(caught.exception.code, "no_exercise_context")
        # Asking and next steps still work without one.
        self.assertEqual(self.tutor("ask", "hi", enrollment=empty).turn.status, "complete")
        self.assertEqual(self.tutor("next_step", enrollment=empty).turn.response_kind, "next_step")

    def test_next_step_is_not_assistance(self) -> None:
        outcome = self.tutor("next_step", exercise=self.mcq)
        self.assertEqual(outcome.turn.response_kind, "next_step")
        self.assertIsNone(outcome.turn.exercise)
        self.assertFalse(TutorExerciseState.objects.exists())
        self.assertIn(
            "[The learner pressed the 'next_step' button", self.last_request().user_message
        )

    def test_latest_attempt_is_linked(self) -> None:
        self.record(self.mcq, "opt-a")
        attempt = self.record(self.mcq, "opt-a")
        outcome = self.tutor("ask", "Why?", self.mcq)
        self.assertEqual(outcome.turn.attempt, attempt)
        self.assertEqual(outcome.turn.response_kind, "feedback")
