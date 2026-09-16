"""Which evaluator handles which response type. Adding a type means adding one line here."""

from apps.evaluation.evaluators.base import Evaluator
from apps.evaluation.evaluators.code import CodeEvaluator
from apps.evaluation.evaluators.fill_gap import FillGapEvaluator
from apps.evaluation.evaluators.multiple_choice import MultipleChoiceEvaluator
from apps.evaluation.evaluators.numeric import NumericEvaluator
from apps.evaluation.evaluators.pending import DeferredTextEvaluator, UnsupportedEvaluator
from apps.exercises.models import ResponseType
from apps.python_runner.evaluator import PythonCodeEvaluator

EVALUATORS: dict[str, Evaluator] = {
    # Deterministic, evaluated now.
    ResponseType.MULTIPLE_CHOICE: MultipleChoiceEvaluator(),
    ResponseType.FILL_GAP: FillGapEvaluator(),
    ResponseType.NUMERIC: NumericEvaluator(),
    # Valid answers kept for a future rubric, language or maths evaluator.
    ResponseType.TEXT: DeferredTextEvaluator("rubric", required_strategy="rubric"),
    ResponseType.TRANSLATION: DeferredTextEvaluator("translation"),
    ResponseType.MATH_EXPRESSION: DeferredTextEvaluator("math_expression"),
    # Code is dispatched by language. Python runs in the isolated runner; other languages
    # are unsupported.
    ResponseType.CODE: CodeEvaluator({"python": PythonCodeEvaluator()}),
    # No evaluation infrastructure yet.
    ResponseType.SPEAKING: UnsupportedEvaluator("speaking"),
    ResponseType.LISTENING: UnsupportedEvaluator("listening"),
}


def get_evaluator(response_type: str) -> Evaluator | None:
    return EVALUATORS.get(response_type)
