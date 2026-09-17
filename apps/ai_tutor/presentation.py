"""Learner-facing tutor payloads: explicit allow-lists, plain text replies.

Provider ids, model names, token usage, latency, prompt versions and context never appear.
"""

from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.types import AssistanceState


def turn_presentation(turn: TutorTurn, assistance: AssistanceState) -> dict:
    return {
        "id": turn.pk,
        "intent": turn.requested_intent,
        "response_kind": turn.response_kind,
        "reply": turn.assistant_message,
        "should_retry": turn.should_retry,
        "exercise_id": turn.exercise_id,
        "attempt_id": turn.attempt_id,
        "assistance": assistance.as_dict(),
        "created_at": turn.created_at.isoformat(),
    }


def history_item(turn: TutorTurn) -> dict:
    return {
        "id": turn.pk,
        "intent": turn.requested_intent,
        "response_kind": turn.response_kind,
        "user_message": turn.user_message,
        "reply": turn.assistant_message,
        "exercise_id": turn.exercise_id,
        "attempt_id": turn.attempt_id,
        "created_at": turn.created_at.isoformat(),
    }
