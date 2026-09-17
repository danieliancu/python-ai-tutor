"""Private Python teaching context: structural facts and deterministic diagnostics only.

Answer material is added exclusively when the server granted a SOLUTION reply. Hidden
tests, expected outputs and evaluation specs are never included at any stage.
"""

from apps.ai_tutor.constants import ResponseKind
from apps.ai_tutor.domains.python.analysis import SYNTAX_ERROR_TYPES, analyze_source
from apps.ai_tutor.domains.python.disclosure import solution_material
from apps.attempts.mistakes import safe_diagnostics
from apps.exercises.models import ResponseType

# Deterministic evaluator reasons → teaching categories. The model never invents one.
REASON_CATEGORIES = {
    "output_mismatch": "wrong_output",
    "wrong_result": "wrong_result",
    "timeout": "timeout",
    "output_limit": "output_limit",
    "missing_function": "missing_function",
    "not_callable": "not_callable",
    "non_serializable_result": "non_serializable_result",
    "invalid_result": "invalid_result",
    "runtime_error": "runtime_error",
    "incorrect_value": "wrong_answer",
    "wrong_option": "wrong_answer",
    "case_mismatch": "wrong_answer",
}

MISTAKE_NOTE = (
    "Mistake codes describe what happened on this one attempt; they are not persistent "
    "misconceptions."
)


def is_python_code(exercise) -> bool:
    content = exercise.content if isinstance(exercise.content, dict) else {}
    return exercise.response_type == ResponseType.CODE and content.get("language") == "python"


def evaluation_facts(attempt) -> dict | None:
    if attempt is None:
        return None
    diagnostics = safe_diagnostics(attempt.diagnostics)
    reason = diagnostics.get("reason")
    error_type = diagnostics.get("error_type")
    if reason == "runtime_error" and error_type in SYNTAX_ERROR_TYPES:
        category = "syntax_error"
    else:
        category = REASON_CATEGORIES.get(reason)
    if category is None and attempt.status == "correct":
        category = "correct"
    return {
        "status": attempt.status,
        "reason": reason,
        "error_type": error_type,
        "category": category,
        "mistake_codes": [mistake.code for mistake in attempt.mistakes.all()],
        "mistake_codes_note": MISTAKE_NOTE,
    }


def teaching_focus(server_context: dict, exercise) -> dict:
    items = server_context.get("misconceptions") or []
    active = [item["code"] for item in items if item.get("status") == "active"]
    watch = [item["code"] for item in items if item.get("status") == "watch"]
    next_action = server_context.get("next_action") or {}
    concept = next_action.get("concept") or {}
    remediating = (
        next_action.get("action") == "remediate" and concept.get("id") == exercise.lesson.concept_id
    )
    return {
        "primary": active[0] if active else None,
        "remediation": remediating,
        "active_misconceptions": active,
        "watch_misconceptions": watch,
    }


def build_python_context(*, exercise, latest_attempt, granted: str, server_context: dict) -> dict:
    if exercise is None:
        return {"domain": "python", "exercise": None}
    source_analysis = None
    if is_python_code(exercise) and latest_attempt is not None:
        source_analysis = analyze_source(latest_attempt.submitted_answer)
    return {
        "domain": "python",
        "response_type": exercise.response_type,
        "learning_mode": exercise.learning_mode,
        "source_analysis": source_analysis,
        "evaluation": evaluation_facts(latest_attempt),
        "teaching_focus": teaching_focus(server_context, exercise),
        "solution_material": (
            solution_material(exercise) if granted == ResponseKind.SOLUTION else None
        ),
    }
