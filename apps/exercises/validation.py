"""Structural checks for an exercise's ``content`` and ``evaluation_spec``.

Deliberately small: both payloads must be objects, answers must never sit in ``content``,
and the response types that already have a known shape get a few type checks. Other types
accept any object until their evaluators exist.
"""

from collections.abc import Callable

from django.core.exceptions import ValidationError

# Keys that reveal answers. They belong in `evaluation_spec`, never in learner-facing content.
ANSWER_KEYS = frozenset(
    {
        "accepted_answers",
        "answer",
        "answers",
        "correct",
        "correct_answer",
        "correct_option",
        "expected_output",
        "is_correct",
        "solution",
    }
)


def _optional_strings(content: dict, *keys: str) -> list[str]:
    return [
        f"“{key}” must be a string."
        for key in keys
        if key in content and not isinstance(content[key], str)
    ]


def _code(content: dict) -> list[str]:
    return _optional_strings(content, "language", "starter_code")


def _fill_gap(content: dict) -> list[str]:
    return _optional_strings(content, "template")


def _translation(content: dict) -> list[str]:
    return _optional_strings(content, "source_language", "target_language", "source_text")


def _multiple_choice(content: dict) -> list[str]:
    options = content.get("options")
    if not isinstance(options, list):
        return ["Multiple choice content needs an “options” list."]
    if len(options) < 2:
        return ["Multiple choice content needs at least two options."]

    errors = []
    seen_ids = set()
    for position, option in enumerate(options, start=1):
        if not isinstance(option, dict):
            errors.append(f"Option {position} must be an object with “id” and “text”.")
            continue
        for key in ("id", "text"):
            value = option.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"Option {position} needs a non-empty string “{key}”.")
        leaked = sorted(ANSWER_KEYS & option.keys())
        if leaked:
            errors.append(
                f"Option {position} must not say whether it is correct ({', '.join(leaked)}); "
                "put the answer in evaluation_spec."
            )
        option_id = option.get("id")
        if isinstance(option_id, str):
            if option_id in seen_ids:
                errors.append(f"Option id “{option_id}” is used more than once.")
            seen_ids.add(option_id)
    return errors


CONTENT_VALIDATORS: dict[str, Callable[[dict], list[str]]] = {
    "code": _code,
    "multiple_choice": _multiple_choice,
    "fill_gap": _fill_gap,
    "translation": _translation,
}


def validate_exercise_json(response_type: str, content: object, evaluation_spec: object) -> None:
    errors: dict[str, list[str]] = {}

    if not isinstance(evaluation_spec, dict):
        errors["evaluation_spec"] = ["Evaluation spec must be a JSON object."]

    if not isinstance(content, dict):
        errors["content"] = ["Content must be a JSON object."]
    else:
        content_errors = []
        leaked = sorted(ANSWER_KEYS & content.keys())
        if leaked:
            content_errors.append(
                f"Content is shown to learners and must not contain {', '.join(leaked)}; "
                "put answers in evaluation_spec."
            )
        validator = CONTENT_VALIDATORS.get(response_type)
        if validator:
            content_errors.extend(validator(content))
        if content_errors:
            errors["content"] = content_errors

    if errors:
        raise ValidationError(errors)
