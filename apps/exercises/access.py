"""Who may use which learning content.

A learner reaches a World's content only through an active or completed enrollment. Paused
or missing enrollments give no access, anonymous visitors get none, and staff status is not
a bypass: staff work with content through the admin.
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet

from apps.curriculum.models import World
from apps.exercises.models import Exercise
from apps.exercises.selectors import published_exercises
from apps.learners.models import Enrollment, EnrollmentStatus

ACCESS_STATUSES = (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)

AnyUser = AbstractBaseUser | AnonymousUser


def _accessible_enrollments(user: AnyUser) -> QuerySet[Enrollment]:
    return Enrollment.objects.filter(learner__user=user, status__in=ACCESS_STATUSES)


def learner_can_access_world(user: AnyUser, world: World) -> bool:
    if not user.is_authenticated:
        return False
    return _accessible_enrollments(user).filter(world=world).exists()


def accessible_exercises(user: AnyUser) -> QuerySet[Exercise]:
    """Published exercises in Worlds the user may currently learn in."""
    if not user.is_authenticated:
        return Exercise.objects.none()
    worlds = _accessible_enrollments(user).values("world_id")
    return published_exercises().filter(lesson__concept__skill__world__in=worlds)


def learner_can_access_exercise(user: AnyUser, exercise: Exercise) -> bool:
    return accessible_exercises(user).filter(pk=exercise.pk).exists()
