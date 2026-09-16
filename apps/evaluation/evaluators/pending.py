"""Response types whose evaluators don't exist yet.

They never judge an answer as correct or incorrect. Text-like answers are accepted for later
review (rubric, language or maths evaluation); code and audio answers are reported as
unsupported. Nothing here runs learner input.
"""

from apps.evaluation import results
from apps.evaluation.evaluators.base import config_error, spec_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise


class DeferredTextEvaluator:
    """A well-formed text answer is accepted for later review."""

    def __init__(self, name: str, *, required_strategy: str | None = None) -> None:
        self.name = name
        self.required_strategy = required_strategy

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        if self.required_strategy and spec_of(exercise).get("strategy") != self.required_strategy:
            raise config_error(exercise, f"strategy must be {self.required_strategy!r}")
        if not isinstance(answer, str):
            return results.invalid(self.name, "invalid_answer_type", "Type your answer as text.")
        if not answer.strip():
            return results.invalid(self.name, "empty_answer", "Type an answer first.")
        return results.review_required(self.name, f"{self.name}_evaluation_pending")


class UnsupportedEvaluator:
    """Automatic evaluation for this response type isn't built yet."""

    def __init__(self, name: str, message: str = results.MESSAGE_UNSUPPORTED) -> None:
        self.name = name
        self.message = message

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        return results.unsupported(self.name, f"{self.name}_evaluator_unavailable", self.message)
