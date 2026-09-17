"""Learner-facing wording for projects. Only safe, server-decided text."""

from apps.projects import selectors
from apps.projects.models import ProjectSubmission

STATE_LABELS = selectors.STATE_LABELS
STAGE_LABELS = {"done": "Done", "available": "Ready", "locked": "Locked"}
# Map stage states onto the existing skill-map dot styles.
STAGE_DOTS = {"done": "mastered", "available": "learning", "locked": "locked"}
STATUS_LABELS = {
    "correct": "✓ Stage passed.",
    "incorrect": "✗ Not quite yet.",
    "invalid": "! Check your code.",
    "unsupported": "! This project can't be checked automatically yet.",
    "unavailable": "! We couldn't check your project right now. Your code is saved.",
}
REASON_TEXT = {
    "output_mismatch": "The program's output isn't what this stage expects yet.",
    "wrong_result": "A function returned a different result than expected.",
    "runtime_error": "Your program stopped with an error.",
    "timeout": "Your program took too long. Look for a loop that never ends.",
    "output_limit": "Your program printed far too much output.",
    "invalid_result": "A function returned a value that can't be checked.",
    "missing_function": "Your program needs a function named {missing}.",
    "not_callable": "Something named like the required function isn't a function.",
    "non_serializable_result": "A function returned a value that can't be checked.",
    "missing_class": "Your program needs a class named {missing}.",
    "missing_method": "Your program needs the method {missing}.",
    "missing_construct": "This stage needs your program to use `{missing}`.",
    "syntax_error": "Python can't read your program yet. Check the syntax.",
    "empty_answer": "Write some code first.",
    "source_too_large": "Your program is too long to check.",
    "invalid_source": "Your code contains characters that can't be run.",
}
IDLE_OUTPUT = "Run / Check your code to see this stage's feedback here."


def feedback_lines(status: str, message: str, diagnostics: dict) -> list[str]:
    lines = [STATUS_LABELS.get(status, "Code saved.")]
    reason = diagnostics.get("reason", "")
    if status != "correct":
        text = REASON_TEXT.get(reason)
        if text:
            lines.append(text.format(missing=diagnostics.get("missing", "")))
        elif message:
            lines.append(message)
        if diagnostics.get("error_type"):
            lines.append(f"Error: {diagnostics['error_type']}")
    return lines


def submission_lines(submission: ProjectSubmission | None) -> list[str]:
    if submission is None:
        return [IDLE_OUTPUT]
    return feedback_lines(submission.status, submission.message, submission.diagnostics or {})


def submission_payload(submission: ProjectSubmission) -> dict:
    return {
        "id": submission.pk,
        "attempt_number": submission.attempt_number,
        "status": submission.status,
        "is_correct": submission.is_correct,
        "score": submission.score,
        "message": submission.message,
        "diagnostics": dict(submission.diagnostics or {}),
        "feedback": submission_lines(submission),
        "submitted_at": submission.submitted_at.isoformat(),
    }
