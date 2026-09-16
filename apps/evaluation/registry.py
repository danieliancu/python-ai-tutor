"""Which evaluator handles which response type. Adding a type means adding one line here."""

from apps.evaluation.evaluators.base import Evaluator
from apps.evaluation.evaluators.fill_gap import FillGapEvaluator
from apps.evaluation.evaluators.multiple_choice import MultipleChoiceEvaluator
from apps.evaluation.evaluators.numeric import NumericEvaluator
from apps.evaluation.evaluators.pending import DeferredTextEvaluator, UnsupportedEvaluator
from apps.exercises.models import ResponseType

EVALUATORS: dict[str, Evaluator] = {
    # Deterministic, evaluated now.
    ResponseType.MULTIPLE_CHOICE: MultipleChoiceEvaluator(),
    ResponseType.FILL_GAP: FillGapEvaluator(),
    ResponseType.NUMERIC: NumericEvaluator(),
    # Valid answers kept for a future rubric, language or maths evaluator.
    ResponseType.TEXT: DeferredTextEvaluator("rubric", required_strategy="rubric"),
    ResponseType.TRANSLATION: DeferredTextEvaluator("translation"),
    ResponseType.MATH_EXPRESSION: DeferredTextEvaluator("math_expression"),
    # No evaluation infrastructure yet. Code runs in a separate runner (Phase 4P).
    ResponseType.CODE: UnsupportedEvaluator("code", "Code evaluation is not available yet."),
    ResponseType.SPEAKING: UnsupportedEvaluator("speaking"),
    ResponseType.LISTENING: UnsupportedEvaluator("listening"),
}


def get_evaluator(response_type: str) -> Evaluator | None:
    return EVALUATORS.get(response_type)
