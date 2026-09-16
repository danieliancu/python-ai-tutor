"""Authenticated JSON endpoints for submitting answers and reading one's own history."""

import json
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from apps.attempts.presentation import attempt_detail, attempt_list_item
from apps.attempts.selectors import attempts_for_learner
from apps.attempts.services import AttemptInputError, record_attempt
from apps.exercises.access import accessible_exercises, learner_can_access_exercise
from apps.exercises.selectors import published_exercises

HISTORY_LIMIT = 50
OPTIONAL_FIELDS = ("hint_level", "used_explanation", "used_solution", "duration_seconds")


def json_error(error: str, status: int, **extra) -> JsonResponse:
    return JsonResponse({"error": error, **extra}, status=status)


def json_login_required(view):
    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error("authentication_required", 401)
        return view(request, *args, **kwargs)

    return wrapper


def _parse_submission(request: HttpRequest) -> dict:
    """The submission fields, or raise ValueError with an error code."""
    try:
        body = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        raise ValueError("malformed_json") from None
    if not isinstance(body, dict):
        raise ValueError("body_must_be_an_object")
    if "answer" not in body:
        raise ValueError("answer_required")
    unknown = set(body) - {"answer", *OPTIONAL_FIELDS}
    if unknown:
        raise ValueError("unknown_fields")
    return body


@require_http_methods(["GET", "POST"])
@json_login_required
def exercise_attempts(request: HttpRequest, exercise_id: int) -> JsonResponse:
    exercise = get_object_or_404(published_exercises(), pk=exercise_id)
    if not learner_can_access_exercise(request.user, exercise):
        return json_error("forbidden", 403)

    if request.method == "GET":
        attempts = attempts_for_learner(request.user).filter(exercise=exercise)[:HISTORY_LIMIT]
        return JsonResponse({"attempts": [attempt_list_item(a) for a in attempts]})

    try:
        body = _parse_submission(request)
    except ValueError as exc:
        return json_error(str(exc), 400)
    try:
        attempt = record_attempt(
            user=request.user,
            exercise=exercise,
            answer=body["answer"],
            **{field: body[field] for field in OPTIONAL_FIELDS if field in body},
        )
    except AttemptInputError as exc:
        return json_error("invalid_input", 400, fields=exc.message_dict)
    except PermissionDenied:
        return json_error("forbidden", 403)
    return JsonResponse(attempt_detail(attempt), status=201)


@require_GET
@json_login_required
def attempt_detail_view(request: HttpRequest, attempt_id: int) -> JsonResponse:
    # Only the owner, and only while the exercise is still available to them.
    attempt = get_object_or_404(
        attempts_for_learner(request.user).filter(exercise__in=accessible_exercises(request.user)),
        pk=attempt_id,
    )
    return JsonResponse(attempt_detail(attempt))
