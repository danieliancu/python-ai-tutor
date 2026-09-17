"""Who may open which project. Always the signed-in learner's own enrollment."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.curriculum.models import World
from apps.exercises.access import accessible_enrollment
from apps.learners.models import Enrollment
from apps.projects.models import Project, ProjectStage


def project_enrollment(user, world_id: int) -> Enrollment:
    """The user's active or completed enrollment in a published World (404 / 403 otherwise)."""
    world = get_object_or_404(World, pk=world_id, is_published=True)
    enrollment = accessible_enrollment(user, world)
    if enrollment is None:
        raise PermissionDenied("You don't have access to this course.")
    return enrollment


def get_project(enrollment: Enrollment, slug: str) -> Project:
    project = (
        Project.objects.filter(world_id=enrollment.world_id, slug=slug, is_published=True)
        .select_related("world")
        .first()
    )
    if project is None:
        raise Http404("Project not found.")
    return project


def get_stage(project: Project, slug: str) -> ProjectStage:
    stage = ProjectStage.objects.filter(project=project, slug=slug, is_published=True).first()
    if stage is None:
        raise Http404("Stage not found.")
    return stage
