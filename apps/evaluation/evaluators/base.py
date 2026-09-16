from typing import Protocol

from apps.evaluation.exceptions import EvaluationConfigurationError
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise


class Evaluator(Protocol):
    """Judges one answer to one exercise, using only the exercise instance (no queries)."""

    name: str

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult: ...


def config_error(exercise: Exercise, problem: str) -> EvaluationConfigurationError:
    return EvaluationConfigurationError(exercise.pk, problem)


def spec_of(exercise: Exercise) -> dict:
    if not isinstance(exercise.evaluation_spec, dict):
        raise config_error(exercise, "evaluation_spec is not an object")
    return exercise.evaluation_spec


def content_of(exercise: Exercise) -> dict:
    if not isinstance(exercise.content, dict):
        raise config_error(exercise, "content is not an object")
    return exercise.content
