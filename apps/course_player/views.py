"""The learner's course player: the existing product shell, backed by real learning state."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.course_player.services import (
    build_course_player_context,
    exercise_in_world,
    progress_context,
)
from apps.curriculum.models import World
from apps.exercises.access import accessible_enrollment
from apps.learners.models import Enrollment


def _enrollment(request: HttpRequest, world_id: int) -> Enrollment:
    """The signed-in learner's own active or completed enrollment in a published World."""
    world = get_object_or_404(World, pk=world_id, is_published=True)
    enrollment = accessible_enrollment(request.user, world)
    if enrollment is None:
        raise PermissionDenied("You don't have access to this course.")
    return enrollment


@login_required
@require_GET
def world(request: HttpRequest, world_id: int) -> HttpResponse:
    enrollment = _enrollment(request, world_id)
    exercise = None
    if "exercise" in request.GET:
        exercise = exercise_in_world(enrollment.world_id, request.GET["exercise"])
        if exercise is None:
            raise Http404("Exercise not found.")
    context = build_course_player_context(enrollment, exercise=exercise)
    context["account_name"] = _account_name(request, enrollment)
    return render(request, "home.html", context)


@login_required
@require_GET
def progress(request: HttpRequest, world_id: int) -> HttpResponse:
    """The left progress panel, server-rendered, for refreshing after an attempt."""
    enrollment = _enrollment(request, world_id)
    current = None
    if "exercise" in request.GET:
        exercise = exercise_in_world(enrollment.world_id, request.GET["exercise"])
        if exercise is None:
            raise Http404("Exercise not found.")
        current = exercise.lesson.concept.skill
    context = progress_context(enrollment, current)
    return render(request, "course_player/partials/progress.html", context)


def _account_name(request: HttpRequest, enrollment: Enrollment) -> str:
    return enrollment.learner.preferred_name or request.user.get_username()
