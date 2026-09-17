"""Server-known AI help: reconstructed from tutor history, never taken from the client alone.

Completed tutor turns are the durable record of help that was actually delivered.
``TutorExerciseState`` is only a materialised copy, repaired on every read. Help completed
after the learner's latest attempt counts towards the *next* attempt. No network calls here.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.ai_tutor.config import get_tutor_config
from apps.ai_tutor.constants import STALE_PENDING_TURN, TurnStatus
from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.pedagogy import apply_granted
from apps.ai_tutor.types import AssistanceState
from apps.attempts.exceptions import AttemptTutorTurnInProgress
from apps.attempts.models import ExerciseAttempt

MIN_STALE_SECONDS = 120


def stale_after() -> timedelta:
    """How long a pending turn may stay in flight before it is treated as abandoned."""
    return timedelta(seconds=max(MIN_STALE_SECONDS, get_tutor_config().timeout_seconds * 4))


def expire_stale_turns(enrollment, exercise, now: datetime | None = None) -> int:
    """Fail abandoned pending turns for this exercise so they stop blocking it."""
    now = now or timezone.now()
    return TutorTurn.objects.filter(
        enrollment=enrollment,
        exercise=exercise,
        status=TurnStatus.PENDING,
        created_at__lt=now - stale_after(),
    ).update(status=TurnStatus.FAILED, error_code=STALE_PENDING_TURN, completed_at=now)


def turn_in_progress(enrollment, exercise, now: datetime | None = None) -> bool:
    expire_stale_turns(enrollment, exercise, now)
    return TutorTurn.objects.filter(
        enrollment=enrollment, exercise=exercise, status=TurnStatus.PENDING
    ).exists()


def latest_attempt(enrollment, exercise) -> ExerciseAttempt | None:
    return (
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise)
        .order_by("-submitted_at", "-id")
        .first()
    )


def reconstruct_assistance(
    enrollment, exercise, *, boundary: ExerciseAttempt | None = None
) -> AssistanceState:
    """Help delivered since the latest attempt, replayed from completed tutor turns."""
    boundary = boundary if boundary is not None else latest_attempt(enrollment, exercise)
    turns = TutorTurn.objects.filter(
        enrollment=enrollment, exercise=exercise, status=TurnStatus.COMPLETE
    )
    if boundary is not None:
        turns = turns.filter(completed_at__gt=boundary.submitted_at)
    state = AssistanceState()
    for kind in turns.order_by("completed_at", "id").values_list("response_kind", flat=True):
        state = apply_granted(state, kind)
    return state


def reconcile_assistance_state(enrollment, exercise) -> AssistanceState:
    """Rebuild the authoritative state and repair the materialised row. Idempotent."""
    boundary = latest_attempt(enrollment, exercise)
    state = reconstruct_assistance(enrollment, exercise, boundary=boundary)
    values = {
        "hint_level": state.hint_level,
        "used_explanation": state.used_explanation,
        "used_solution": state.used_solution,
        "last_attempt": boundary,
    }
    with transaction.atomic():
        row = (
            TutorExerciseState.objects.select_for_update()
            .filter(enrollment=enrollment, exercise=exercise)
            .first()
        )
        if row is None:
            TutorExerciseState.objects.create(enrollment=enrollment, exercise=exercise, **values)
        elif any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            row.save()
    return state


def reconcile_outcome(enrollment, exercise) -> str:
    """Like ``reconcile_assistance_state`` but reports created / updated / unchanged."""
    before = (
        TutorExerciseState.objects.filter(enrollment=enrollment, exercise=exercise)
        .values("hint_level", "used_explanation", "used_solution", "last_attempt_id")
        .first()
    )
    reconcile_assistance_state(enrollment, exercise)
    after = (
        TutorExerciseState.objects.filter(enrollment=enrollment, exercise=exercise)
        .values("hint_level", "used_explanation", "used_solution", "last_attempt_id")
        .first()
    )
    if before is None:
        return "created"
    return "unchanged" if before == after else "updated"


def record_attempt_boundary(attempt: ExerciseAttempt) -> None:
    """A stored attempt starts a fresh help record (the cache is repaired from history)."""
    reconcile_assistance_state(attempt.enrollment, attempt.exercise)


def authoritative_for_attempt(
    enrollment,
    exercise,
    *,
    hint_level: int,
    used_explanation: bool,
    used_solution: bool,
    now: datetime | None = None,
) -> dict:
    """Assistance to store with a new attempt: client values raised to server-known help.

    Raises ``AttemptTutorTurnInProgress`` while a tutor reply for this exercise is being
    generated, because its help might still belong to this submission. Any other failure
    propagates, so the caller can refuse to store the attempt.
    """
    if turn_in_progress(enrollment, exercise, now):
        raise AttemptTutorTurnInProgress()
    server = reconstruct_assistance(enrollment, exercise)
    return {
        "hint_level": max(hint_level, server.hint_level),
        "used_explanation": used_explanation or server.used_explanation,
        "used_solution": used_solution or server.used_solution,
    }
