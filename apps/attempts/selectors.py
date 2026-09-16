from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Count, QuerySet

from apps.attempts.models import AttemptMistake, ExerciseAttempt
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment


def attempts_for_learner(user: AbstractBaseUser) -> QuerySet[ExerciseAttempt]:
    """All of one learner's attempts, newest first, ready for presentation."""
    return (
        ExerciseAttempt.objects.filter(enrollment__learner__user=user)
        .select_related("exercise")
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")
    )


def attempt_history_for_exercise(
    enrollment: Enrollment, exercise: Exercise
) -> QuerySet[ExerciseAttempt]:
    return (
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise)
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")
    )


def latest_attempt_for_exercise(
    enrollment: Enrollment, exercise: Exercise
) -> ExerciseAttempt | None:
    return (
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise)
        .order_by("-attempt_number")
        .first()
    )


def recent_attempts_for_enrollment(
    enrollment: Enrollment, limit: int = 20
) -> list[ExerciseAttempt]:
    return list(
        ExerciseAttempt.objects.filter(enrollment=enrollment)
        .select_related("exercise")
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")[:limit]
    )


def mistake_counts_for_enrollment(enrollment: Enrollment) -> dict[str, int]:
    """How often each mistake code occurred in this enrollment (one query)."""
    rows = (
        AttemptMistake.objects.filter(attempt__enrollment=enrollment)
        .values("code")
        .annotate(count=Count("id"))
        .order_by("code")
    )
    return {row["code"]: row["count"] for row in rows}
