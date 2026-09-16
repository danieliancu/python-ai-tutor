"""Learner-facing views of attempts: explicit allow-lists, never whole model instances."""

from apps.attempts.mistakes import safe_diagnostics
from apps.attempts.models import ExerciseAttempt


def attempt_list_item(attempt: ExerciseAttempt) -> dict:
    return {
        "id": attempt.pk,
        "exercise_id": attempt.exercise_id,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "score": attempt.score,
        "is_correct": attempt.is_correct,
        "evaluator": attempt.evaluator,
        "message": attempt.message,
        "diagnostics": safe_diagnostics(attempt.diagnostics),
        "mistakes": [
            {"code": mistake.code, "details": safe_diagnostics(mistake.details)}
            for mistake in attempt.mistakes.all()
        ],
        "hint_level": attempt.hint_level,
        "used_explanation": attempt.used_explanation,
        "used_solution": attempt.used_solution,
        "duration_seconds": attempt.duration_seconds,
        "submitted_at": attempt.submitted_at.isoformat(),
    }


def attempt_detail(attempt: ExerciseAttempt) -> dict:
    """The list item plus the learner's own submitted answer."""
    return {**attempt_list_item(attempt), "submitted_answer": attempt.submitted_answer}
