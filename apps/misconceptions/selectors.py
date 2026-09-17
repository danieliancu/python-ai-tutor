"""Read-only queries over misconception state. Ordering is descriptive, not a recommendation."""

from django.db.models import QuerySet

from apps.curriculum.models import Concept
from apps.learners.models import Enrollment
from apps.misconceptions.models import MisconceptionState, MisconceptionStatus

STRONGEST_FIRST = ("-confidence_score", "-last_seen_at", "code")


def _states(enrollment: Enrollment) -> QuerySet[MisconceptionState]:
    return MisconceptionState.objects.filter(enrollment=enrollment).select_related("concept__skill")


def misconceptions_for_concept(
    enrollment: Enrollment, concept: Concept
) -> QuerySet[MisconceptionState]:
    return _states(enrollment).filter(concept=concept).order_by(*STRONGEST_FIRST)


def active_misconceptions(enrollment: Enrollment) -> QuerySet[MisconceptionState]:
    return _states(enrollment).filter(status=MisconceptionStatus.ACTIVE).order_by(*STRONGEST_FIRST)


def watch_misconceptions(enrollment: Enrollment) -> QuerySet[MisconceptionState]:
    return _states(enrollment).filter(status=MisconceptionStatus.WATCH).order_by(*STRONGEST_FIRST)


def resolved_misconceptions(enrollment: Enrollment) -> QuerySet[MisconceptionState]:
    return (
        _states(enrollment)
        .filter(status=MisconceptionStatus.RESOLVED)
        .order_by("-resolved_at", "code")
    )


def misconceptions_for_world(enrollment: Enrollment) -> QuerySet[MisconceptionState]:
    """States in the enrollment's currently published concepts."""
    return (
        _states(enrollment)
        .filter(
            concept__is_published=True,
            concept__skill__is_published=True,
            concept__skill__world_id=enrollment.world_id,
        )
        .order_by(*STRONGEST_FIRST)
    )


def top_active_misconceptions(enrollment: Enrollment, limit: int = 5) -> list[MisconceptionState]:
    return list(active_misconceptions(enrollment)[:limit])
