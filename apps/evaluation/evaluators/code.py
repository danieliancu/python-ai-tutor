from apps.evaluation import results
from apps.evaluation.evaluators.base import Evaluator, content_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise


class CodeEvaluator:
    """Routes a CODE exercise to the evaluator for its ``content["language"]``.

    Languages without an evaluator are reported as unsupported, never judged.
    """

    name = "code"

    def __init__(self, language_evaluators: dict[str, Evaluator]) -> None:
        self.language_evaluators = language_evaluators

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        language = content_of(exercise).get("language")
        evaluator = self.language_evaluators.get(language) if isinstance(language, str) else None
        if evaluator is None:
            return results.unsupported(
                self.name,
                "code_language_unsupported",
                "Code evaluation is not available for this language yet.",
            )
        return evaluator.evaluate(exercise, answer)
