"""The learner-facing view of an EvaluationResult: an explicit allow-list.

Diagnostics and the evaluator name stay internal.
"""

from apps.evaluation.results import EvaluationResult

PUBLIC_FIELDS = ("status", "score", "is_correct", "message")


def evaluation_result_presentation(result: EvaluationResult) -> dict:
    return {
        "status": str(result.status),
        "score": result.score,
        "is_correct": result.is_correct,
        "message": result.message,
    }
