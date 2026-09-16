"""Entry points for evaluating an answer to an exercise."""

import logging

from django.core.exceptions import PermissionDenied

from apps.evaluation import results
from apps.evaluation.exceptions import (
    EvaluationConfigurationError,
    EvaluationError,
    EvaluationUnavailable,
)
from apps.evaluation.presentation import evaluation_result_presentation
from apps.evaluation.registry import get_evaluator
from apps.evaluation.results import EvaluationResult
from apps.exercises.access import AnyUser, learner_can_access_exercise
from apps.exercises.models import Exercise

logger = logging.getLogger(__name__)


def evaluate_exercise(exercise: Exercise, answer: object) -> EvaluationResult:
    """Judge ``answer`` with the evaluator for the exercise's response type.

    Pure: no database access and nothing is stored. Raises EvaluationConfigurationError
    when the exercise itself is misconfigured, which is never reported as a wrong answer.
    """
    evaluator = get_evaluator(exercise.response_type)
    if evaluator is None:
        return results.unsupported("none", "no_evaluator")
    return evaluator.evaluate(exercise, answer)


def evaluate_for_learner(user: AnyUser, exercise: Exercise, answer: object) -> dict:
    """Authorise, evaluate and return only what a learner may see."""
    if not learner_can_access_exercise(user, exercise):
        raise PermissionDenied("You don't have access to this exercise.")
    try:
        result = evaluate_exercise(exercise, answer)
    except EvaluationConfigurationError as exc:
        logger.error("Evaluation failed for exercise %s: %s", exc.exercise_id, exc.problem)
        raise EvaluationUnavailable() from exc
    except EvaluationError as exc:
        # Infrastructure trouble (e.g. the code runner is down) is never the learner's fault.
        logger.error("Evaluation unavailable for exercise %s: %s", exercise.pk, exc)
        raise EvaluationUnavailable() from exc
    return evaluation_result_presentation(result)
