"""Structural checks for an exercise's ``content`` and ``evaluation_spec``.

Deliberately small: both payloads must be objects, answers must never sit in ``content``,
response types with a known content shape get a few type checks, and response types with an
evaluation contract (multiple choice, fill gap, numeric, text rubric, code) have their
``evaluation_spec`` checked. Other types accept any object until their evaluators exist.

This module only checks structure. Judging answers is the job of ``apps.evaluation``.
"""

import math
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

CODE_STRATEGIES = ("stdout", "function")


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


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _non_empty_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _multiple_choice_spec(spec: dict, content: dict) -> list[str]:
    correct = spec.get("correct_option")
    if not isinstance(correct, str) or not correct.strip():
        return ["Multiple choice needs “correct_option”, the id of the right option."]
    option_ids = {
        option.get("id") for option in content.get("options", []) if isinstance(option, dict)
    }
    if correct not in option_ids:
        return [f"“correct_option” {correct!r} is not one of the option ids."]
    return []


def _fill_gap_spec(spec: dict, content: dict) -> list[str]:
    errors = []
    if not _non_empty_strings(spec.get("accepted_answers")):
        errors.append("Fill the gap needs “accepted_answers”: a list of non-empty strings.")
    if "case_sensitive" in spec and not isinstance(spec["case_sensitive"], bool):
        errors.append("“case_sensitive” must be true or false.")
    return errors


def _numeric_spec(spec: dict, content: dict) -> list[str]:
    errors = []
    if not _is_number(spec.get("expected")):
        errors.append("Numeric exercises need “expected”: a finite number.")
    if "tolerance" in spec and not (_is_number(spec["tolerance"]) and spec["tolerance"] >= 0):
        errors.append("“tolerance” must be a finite number of zero or more.")
    return errors


def _text_spec(spec: dict, content: dict) -> list[str]:
    errors = []
    if spec.get("strategy") != "rubric":
        errors.append('Text exercises need “strategy”: "rubric".')
    if not _non_empty_strings(spec.get("criteria")):
        errors.append("A rubric needs “criteria”: a list of non-empty strings.")
    return errors


def _code_test_errors(strategy: str, position: int, test: object) -> list[str]:
    if not isinstance(test, dict):
        return [f"Test {position} must be an object."]
    if strategy == "stdout":
        if not all(isinstance(test.get(key), str) for key in ("stdin", "expected_stdout")):
            return [f"Test {position} needs string “stdin” and “expected_stdout”."]
        return []
    if not (
        isinstance(test.get("args"), list)
        and isinstance(test.get("kwargs"), dict)
        and "expected" in test
    ):
        return [f"Test {position} needs list “args”, object “kwargs” and “expected”."]
    return []


def _code_spec(spec: dict, content: dict) -> list[str]:
    strategy = spec.get("strategy")
    if strategy not in CODE_STRATEGIES:
        return [f"Code exercises need “strategy”: one of {', '.join(CODE_STRATEGIES)}."]
    errors = []
    tests = spec.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append("Code exercises need a non-empty “tests” list.")
    else:
        for position, test in enumerate(tests, start=1):
            errors.extend(_code_test_errors(strategy, position, test))
    if strategy == "function":
        name = spec.get("function_name")
        if not isinstance(name, str) or not name.isidentifier():
            errors.append("The function strategy needs “function_name”, a valid identifier.")
    if "reference_solution" in spec and not isinstance(spec["reference_solution"], str):
        errors.append("“reference_solution” must be a string.")
    return errors


# Evaluation contracts per response type. Types not listed here (translation, maths
# expressions, speaking, listening) get their contracts together with their evaluators.
SPEC_VALIDATORS: dict[str, Callable[[dict, dict], list[str]]] = {
    "multiple_choice": _multiple_choice_spec,
    "fill_gap": _fill_gap_spec,
    "numeric": _numeric_spec,
    "text": _text_spec,
    "code": _code_spec,
}


def validate_exercise_json(
    response_type: str,
    content: object,
    evaluation_spec: object,
    *,
    require_spec: bool = False,
) -> None:
    """Validate both payloads.

    A non-empty evaluation spec is always checked against its type's contract. An empty
    one is accepted only when ``require_spec`` is False, i.e. for unpublished drafts.
    """
    errors: dict[str, list[str]] = {}

    if not isinstance(evaluation_spec, dict):
        errors["evaluation_spec"] = ["Evaluation spec must be a JSON object."]
    elif evaluation_spec or require_spec:
        spec_validator = SPEC_VALIDATORS.get(response_type)
        if spec_validator:
            spec_errors = spec_validator(
                evaluation_spec, content if isinstance(content, dict) else {}
            )
            if spec_errors:
                errors["evaluation_spec"] = spec_errors

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
