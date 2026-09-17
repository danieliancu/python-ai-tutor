"""Stage-gated answer material and a high-precision guard against leaking it early."""

import re

from apps.exercises.models import ResponseType

MIN_REFERENCE_CHARS = 12
FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def solution_material(exercise) -> dict | None:
    """The minimum authored answer needed to teach a full solution. Never tests or specs."""
    spec = exercise.evaluation_spec if isinstance(exercise.evaluation_spec, dict) else {}
    content = exercise.content if isinstance(exercise.content, dict) else {}
    kind = exercise.response_type
    if kind == ResponseType.CODE:
        reference = spec.get("reference_solution")
        return {"reference_solution": reference} if isinstance(reference, str) else None
    if kind == ResponseType.FILL_GAP:
        answers = spec.get("accepted_answers")
        if isinstance(answers, list) and answers:
            return {"accepted_answers": [a for a in answers if isinstance(a, str)]}
        return None
    if kind == ResponseType.MULTIPLE_CHOICE:
        correct = spec.get("correct_option")
        if not isinstance(correct, str):
            return None
        text = next(
            (
                option.get("text")
                for option in content.get("options", [])
                if isinstance(option, dict) and option.get("id") == correct
            ),
            None,
        )
        return {"correct_option": correct, "correct_option_text": text}
    if kind == ResponseType.NUMERIC and "expected" in spec:
        return {"expected": spec.get("expected"), "tolerance": spec.get("tolerance", 0)}
    return None


def _normalised_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _contains(haystack: list[str], needle: list[str]) -> bool:
    size = len(needle)
    return any(haystack[i : i + size] == needle for i in range(len(haystack) - size + 1))


def leaks_reference(reply: str, reference: object) -> bool:
    """True when the whole reference solution appears in the reply (whitespace-insensitive).

    Checks fenced code blocks and the full text. Deliberately exact: partial overlaps and
    similar-but-different code are not treated as leaks.
    """
    if not isinstance(reference, str) or not isinstance(reply, str):
        return False
    needle = _normalised_lines(reference)
    if not needle or sum(len(line.replace(" ", "")) for line in needle) < MIN_REFERENCE_CHARS:
        return False
    candidates = [block for block in FENCE.findall(reply)] + [reply]
    return any(_contains(_normalised_lines(text), needle) for text in candidates)
