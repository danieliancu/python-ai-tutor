"""Authenticated tutor endpoints (session login, CSRF-protected POST)."""

import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from apps.ai_tutor.constants import HISTORY_DEFAULT, HISTORY_MAX, Intent
from apps.ai_tutor.presentation import history_item, turn_presentation
from apps.ai_tutor.selectors import recent_completed_turns
from apps.ai_tutor.services import TutorRequestError, request_tutor_turn
from apps.attempts.views import json_error, json_login_required
from apps.curriculum.models import World
from apps.exercises.access import accessible_enrollment

ALLOWED_FIELDS = frozenset({"message", "intent", "exercise_id"})
UNAVAILABLE_MESSAGE = "The tutor is temporarily unavailable."


def _parse(request: HttpRequest) -> dict:
    try:
        body = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        raise ValueError("malformed_json") from None
    if not isinstance(body, dict):
        raise ValueError("body_must_be_an_object")
    if set(body) - ALLOWED_FIELDS:
        raise ValueError("unknown_fields")
    exercise_id = body.get("exercise_id")
    if exercise_id is not None and (
        not isinstance(exercise_id, int) or isinstance(exercise_id, bool)
    ):
        raise ValueError("invalid_exercise_id")
    return body


def _limit(request: HttpRequest) -> int:
    raw = request.GET.get("limit")
    if raw is None:
        return HISTORY_DEFAULT
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError("invalid_limit")
    return min(int(raw), HISTORY_MAX)


@require_http_methods(["GET", "POST"])
@json_login_required
def tutor_turns(request: HttpRequest, world_id: int) -> JsonResponse:
    world = get_object_or_404(World, pk=world_id, is_published=True)
    enrollment = accessible_enrollment(request.user, world)
    if enrollment is None:
        return json_error("forbidden", 403)

    if request.method == "GET":
        try:
            limit = _limit(request)
        except ValueError as exc:
            return json_error(str(exc), 400)
        turns = recent_completed_turns(enrollment, limit)
        return JsonResponse({"turns": [history_item(turn) for turn in turns]})

    try:
        body = _parse(request)
    except ValueError as exc:
        return json_error(str(exc), 400)
    try:
        outcome = request_tutor_turn(
            enrollment,
            intent=body.get("intent", Intent.ASK),
            message=body.get("message", ""),
            exercise_id=body.get("exercise_id"),
        )
    except TutorRequestError as exc:
        if exc.status == 503:
            return json_error(exc.code, 503, message=UNAVAILABLE_MESSAGE)
        return json_error(exc.code, exc.status)
    return JsonResponse(turn_presentation(outcome.turn, outcome.assistance), status=201)
