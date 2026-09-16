"""Turn an evaluation result into safe, stored mistake signals.

Only short reason codes produced by the evaluators are kept (plus an exception class name for
runtime errors). Nothing here can carry answers, tests or evaluation specs.
"""

import re
from collections.abc import Mapping

from apps.evaluation.results import EvaluationResult, EvaluationStatus

# Learner-mistake reason codes the evaluators emit today.
MISTAKE_CODES = frozenset(
    {
        # multiple choice
        "wrong_option",
        "invalid_option",
        # fill gap / numeric / text-like
        "incorrect_value",
        "case_mismatch",
        "invalid_numeric_input",
        "invalid_answer_type",
        "empty_answer",
        # Python code
        "output_mismatch",
        "runtime_error",
        "timeout",
        "output_limit",
        "wrong_result",
        "missing_function",
        "not_callable",
        "non_serializable_result",
        "invalid_result",
        "invalid_source",
        "source_too_large",
    }
)

SAFE_DIAGNOSTIC_KEYS = frozenset({"reason", "error_type"})
SAFE_CODE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MISTAKE_STATUSES = frozenset({EvaluationStatus.INCORRECT, EvaluationStatus.INVALID})


def is_safe_code(value: object) -> bool:
    return isinstance(value, str) and bool(SAFE_CODE.match(value))


def is_safe_details(value: object) -> bool:
    """A dict whose keys are known diagnostic keys and whose values are short codes."""
    return isinstance(value, dict) and all(
        key in SAFE_DIAGNOSTIC_KEYS and is_safe_code(item) for key, item in value.items()
    )


def safe_diagnostics(diagnostics: Mapping) -> dict:
    """Keep only allow-listed keys with code-like values; drop everything else."""
    return {
        key: value
        for key, value in diagnostics.items()
        if key in SAFE_DIAGNOSTIC_KEYS and is_safe_code(value)
    }


def extract_mistakes_from_result(result: EvaluationResult) -> list[dict]:
    """Mistake rows for a judged-wrong or malformed answer; empty for anything else."""
    if result.status not in MISTAKE_STATUSES:
        return []
    diagnostics = safe_diagnostics(result.diagnostics)
    code = diagnostics.get("reason")
    if code not in MISTAKE_CODES:
        return []
    details = {}
    if code == "runtime_error" and "error_type" in diagnostics:
        details["error_type"] = diagnostics["error_type"]
    return [{"code": code, "details": details}]
