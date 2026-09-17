from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.services import request_tutor_turn
from apps.learner_intelligence.tests.helpers import IntelligenceFixtures

ENABLED = {
    "ENABLED": True,
    "OPENAI_API_KEY": "sk-test-not-a-real-key",
    "OPENAI_MODEL": "gpt-5.6-luna",
}
FORBIDDEN_KEYS = {
    "evaluation_spec",
    "correct_option",
    "accepted_answers",
    "expected",
    "expected_stdout",
    "reference_solution",
    "reference_answers",
    "tests",
    "misconception_evidence",
    "evidence",
    "provider_response_id",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "prompt_version",
    "api_key",
    "container_id",
}


def keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(keys(v) for v in value.values()))
    if isinstance(value, list | tuple):
        return set().union(*(keys(v) for v in value))
    return set()


class TutorFixtures(IntelligenceFixtures):
    """AttemptFixtures (Python, English and Maths worlds) with the tutor enabled."""

    def setUp(self) -> None:
        super().setUp()
        self.enterContext(override_settings(AI_TUTOR=ENABLED))
        self.provider = FakeTutorProvider()

    def tutor(self, intent="ask", message="", exercise=None, *, enrollment=None, **kwargs):
        kwargs.setdefault("provider", self.provider)
        if message == "" and intent == "ask":
            message = "Can you help me?"
        return request_tutor_turn(
            enrollment or self.enrollment,
            intent=intent,
            message=message,
            exercise_id=exercise.pk if exercise is not None else None,
            **kwargs,
        )

    def last_request(self):
        return self.provider.requests[-1]

    def old_turn(self, enrollment=None, *, seconds_ago=5, status="complete", **fields):
        fields.setdefault("requested_intent", "ask")
        fields.setdefault("response_kind", "guidance" if status == "complete" else "")
        return TutorTurn.objects.create(
            enrollment=enrollment or self.enrollment,
            status=status,
            prompt_version=1,
            created_at=timezone.now() - timedelta(seconds=seconds_ago),
            **fields,
        )
