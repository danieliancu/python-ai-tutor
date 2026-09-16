"""The one place where learner attempts are recorded."""

import json
import logging

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.attempts.mistakes import extract_mistakes_from_result, safe_diagnostics
from apps.attempts.models import (
    MAX_DURATION_SECONDS,
    MAX_HINT_LEVEL,
    AttemptMistake,
    AttemptStatus,
    ExerciseAttempt,
)
from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.exceptions import EvaluationError
from apps.evaluation.registry import get_evaluator
from apps.exercises.access import ACCESS_STATUSES
from apps.exercises.models import Exercise
from apps.exercises.selectors import published_exercises
from apps.learners.models import Enrollment

logger = logging.getLogger(__name__)

MAX_ANSWER_BYTES = 100_000
UNAVAILABLE_MESSAGE = "We couldn't check your answer right now."
NUMBERING_RETRIES = 3


class AttemptInputError(ValidationError):
    """The attempt's own inputs (not the answer's correctness) are unusable."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_attempt_inputs(
    *,
    answer: object,
    hint_level: object,
    used_explanation: object,
    used_solution: object,
    duration_seconds: object,
) -> None:
    errors = {}
    if not _is_int(hint_level) or not 0 <= hint_level <= MAX_HINT_LEVEL:
        errors["hint_level"] = f"Must be a whole number from 0 to {MAX_HINT_LEVEL}."
    for name, value in (("used_explanation", used_explanation), ("used_solution", used_solution)):
        if not isinstance(value, bool):
            errors[name] = "Must be true or false."
    if duration_seconds is not None and (
        not _is_int(duration_seconds) or not 0 <= duration_seconds <= MAX_DURATION_SECONDS
    ):
        errors["duration_seconds"] = (
            f"Must be empty or a whole number from 0 to {MAX_DURATION_SECONDS}."
        )
    try:
        encoded = json.dumps(answer, allow_nan=False)
    except (TypeError, ValueError):
        errors["answer"] = "Must be JSON data (text, number, true/false, null, list or object)."
    else:
        if len(encoded.encode("utf-8")) > MAX_ANSWER_BYTES:
            errors["answer"] = "Is too large."
    if errors:
        raise AttemptInputError(errors)


def resolve_enrollment(user: AbstractBaseUser | AnonymousUser, exercise: Exercise) -> Enrollment:
    """The learner's own enrollment that grants access to ``exercise``, or PermissionDenied."""
    if not user.is_authenticated:
        raise PermissionDenied("Sign in to submit answers.")
    if not published_exercises().filter(pk=exercise.pk).exists():
        raise PermissionDenied("This exercise isn't available.")
    enrollment = Enrollment.objects.filter(
        learner__user=user,
        world__skills__concepts__lessons__exercises=exercise,
        status__in=ACCESS_STATUSES,
    ).first()
    if enrollment is None:
        raise PermissionDenied("You don't have access to this exercise.")
    return enrollment


def _evaluate(exercise: Exercise, answer: object) -> dict:
    """Evaluation snapshot fields. Infrastructure trouble is recorded, never blamed on learners."""
    try:
        result = evaluate_exercise(exercise, answer)
    except EvaluationError as exc:
        logger.error("Could not evaluate an attempt for exercise %s: %s", exercise.pk, exc)
        evaluator = get_evaluator(exercise.response_type)
        return {
            "status": AttemptStatus.UNAVAILABLE,
            "score": None,
            "is_correct": None,
            "evaluator": getattr(evaluator, "name", "unknown"),
            "message": UNAVAILABLE_MESSAGE,
            "diagnostics": {"reason": "evaluation_unavailable"},
            "mistakes": [],
        }
    return {
        "status": AttemptStatus(str(result.status)),
        "score": result.score,
        "is_correct": result.is_correct,
        "evaluator": result.evaluator,
        "message": result.message,
        "diagnostics": safe_diagnostics(result.diagnostics),
        "mistakes": extract_mistakes_from_result(result),
    }


def record_attempt(
    *,
    user: AbstractBaseUser | AnonymousUser,
    exercise: Exercise,
    answer: object,
    hint_level: int = 0,
    used_explanation: bool = False,
    used_solution: bool = False,
    duration_seconds: int | None = None,
) -> ExerciseAttempt:
    """Check access, evaluate the answer and store the attempt with its mistakes."""
    validate_attempt_inputs(
        answer=answer,
        hint_level=hint_level,
        used_explanation=used_explanation,
        used_solution=used_solution,
        duration_seconds=duration_seconds,
    )
    enrollment = resolve_enrollment(user, exercise)
    # Evaluate before touching the database: code evaluation can take seconds.
    snapshot = _evaluate(exercise, answer)
    mistakes = snapshot.pop("mistakes")

    for retry in range(NUMBERING_RETRIES):
        try:
            with transaction.atomic():
                return _store(
                    enrollment,
                    exercise,
                    snapshot,
                    mistakes,
                    submitted_answer=answer,
                    hint_level=hint_level,
                    used_explanation=used_explanation,
                    used_solution=used_solution,
                    duration_seconds=duration_seconds,
                )
        except (IntegrityError, ValidationError) as exc:
            # Another submission took the same attempt number; try the next one.
            if retry == NUMBERING_RETRIES - 1 or not _is_numbering_conflict(exc):
                raise
    raise AssertionError("unreachable")


def _is_numbering_conflict(exc: Exception) -> bool:
    if isinstance(exc, IntegrityError):
        return True
    return isinstance(exc, ValidationError) and "__all__" in getattr(exc, "message_dict", {})


def _store(enrollment, exercise, snapshot, mistakes, **fields) -> ExerciseAttempt:
    # Serialise numbering per enrollment (a no-op on SQLite, which serialises writes anyway).
    Enrollment.objects.select_for_update().filter(pk=enrollment.pk).first()
    last = ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise).aggregate(
        last=Max("attempt_number")
    )["last"]
    attempt = ExerciseAttempt.objects.create(
        enrollment=enrollment,
        exercise=exercise,
        attempt_number=(last or 0) + 1,
        **snapshot,
        **fields,
    )
    for mistake in mistakes:
        AttemptMistake.objects.create(attempt=attempt, **mistake)
    return attempt
