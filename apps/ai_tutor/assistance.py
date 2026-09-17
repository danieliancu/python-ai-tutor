"""Server-known AI help, merged into attempts so tutor help can't be hidden by the client.

Help given after an attempt counts towards the *next* attempt: every stored attempt resets the
record. No network calls happen here.
"""

from django.db import transaction

from apps.ai_tutor.models import TutorExerciseState
from apps.ai_tutor.pedagogy import apply_granted
from apps.ai_tutor.types import AssistanceState


def _state(row: TutorExerciseState | None) -> AssistanceState:
    if row is None:
        return AssistanceState()
    return AssistanceState(row.hint_level, row.used_explanation, row.used_solution)


def assistance_for(enrollment, exercise) -> AssistanceState:
    return _state(
        TutorExerciseState.objects.filter(enrollment=enrollment, exercise=exercise).first()
    )


def merge_with_client(
    enrollment,
    exercise,
    *,
    hint_level: int,
    used_explanation: bool,
    used_solution: bool,
) -> dict:
    """Client-reported help plus server-known tutor help (tutor help is a minimum)."""
    server = assistance_for(enrollment, exercise)
    return {
        "hint_level": max(hint_level, server.hint_level),
        "used_explanation": used_explanation or server.used_explanation,
        "used_solution": used_solution or server.used_solution,
    }


def record_attempt_boundary(attempt) -> None:
    """A new attempt starts a fresh assistance record for its exercise."""
    TutorExerciseState.objects.update_or_create(
        enrollment=attempt.enrollment,
        exercise=attempt.exercise,
        defaults={
            "hint_level": 0,
            "used_explanation": False,
            "used_solution": False,
            "last_attempt": attempt,
        },
    )


def apply_turn(enrollment, exercise, kind: str) -> AssistanceState:
    """Record a successful tutor reply at ``kind``; returns the resulting state."""
    with transaction.atomic():
        row, _ = TutorExerciseState.objects.select_for_update().get_or_create(
            enrollment=enrollment, exercise=exercise
        )
        updated = apply_granted(_state(row), kind)
        if updated != _state(row):
            row.hint_level = updated.hint_level
            row.used_explanation = updated.used_explanation
            row.used_solution = updated.used_solution
            row.save()
        return updated
