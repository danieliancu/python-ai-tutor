from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.attempts.views import json_error, json_login_required
from apps.curriculum.models import World
from apps.exercises.access import accessible_enrollment
from apps.next_action.engine import next_action_for_enrollment
from apps.next_action.presentation import decision_presentation


@require_GET
@json_login_required
def next_action(request: HttpRequest, world_id: int) -> JsonResponse:
    """What the signed-in learner should do next in this World. Read-only, never stored."""
    world = get_object_or_404(World, pk=world_id, is_published=True)
    enrollment = accessible_enrollment(request.user, world)
    if enrollment is None:
        return json_error("forbidden", 403)
    decision = next_action_for_enrollment(enrollment)
    return JsonResponse(decision_presentation(decision, enrollment))
