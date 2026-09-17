from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.attempts.views import json_error, json_login_required
from apps.curriculum.models import World
from apps.exercises.access import ACCESS_STATUSES
from apps.learner_intelligence.presentation import student_state_for_enrollment
from apps.learners.models import Enrollment


@require_GET
@json_login_required
def learning_state(request: HttpRequest, world_id: int) -> JsonResponse:
    """The signed-in learner's derived Student State for one World. Read-only."""
    world = get_object_or_404(World, pk=world_id, is_published=True)
    enrollment = Enrollment.objects.filter(
        learner__user=request.user, world=world, status__in=ACCESS_STATUSES
    ).first()
    if enrollment is None:
        return json_error("forbidden", 403)
    return JsonResponse(student_state_for_enrollment(enrollment))
