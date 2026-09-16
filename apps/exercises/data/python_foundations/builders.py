"""Helpers that turn compact Python-pack definitions into generic Exercise field values.

These are content-authoring conveniences for the Python pack only; the Exercise model knows
nothing about them. Answers, tests and reference solutions always go into
``evaluation_spec``; ``content`` only holds what the learner is shown.
"""

import re
from textwrap import dedent

RECOGNISE = "recognise"
COMPLETE = "complete"
FIX = "fix"
CREATE = "create"

OPTION_IDS = "abcdefgh"

# The gap in a fill-gap template: a standalone "__", never part of a name like __init__.
GAP_PATTERN = re.compile(r"(?<!\w)__(?!\w)")


def code(text: str) -> str:
    """Dedent a triple-quoted code block and make it end with exactly one newline."""
    return dedent(text).strip("\n") + "\n"


def _exercise(
    slug: str,
    title: str,
    prompt: str,
    *,
    instructions: str,
    response_type: str,
    mode: str,
    seconds: int,
    content: dict,
    spec: dict,
    misconceptions: tuple[str, ...],
) -> dict:
    if misconceptions:
        spec["misconceptions"] = list(misconceptions)
    return {
        "slug": slug,
        "title": title,
        "prompt": prompt,
        "instructions": instructions,
        "response_type": response_type,
        "learning_mode": mode,
        "content": content,
        "evaluation_spec": spec,
        "target_seconds": seconds,
    }


def mcq(
    slug: str,
    title: str,
    prompt: str,
    *,
    options: list[str],
    correct: str,
    explanation: str,
    seconds: int,
    snippet: str = "",
    mode: str = RECOGNISE,
    instructions: str = "Choose one answer.",
    misconceptions: tuple[str, ...] = (),
) -> dict:
    content = {"options": [{"id": OPTION_IDS[i], "text": text} for i, text in enumerate(options)]}
    if snippet:
        content = {"code": code(snippet), **content}
    return _exercise(
        slug,
        title,
        prompt,
        instructions=instructions,
        response_type="multiple_choice",
        mode=mode,
        seconds=seconds,
        content=content,
        spec={"correct_option": correct, "explanation": explanation},
        misconceptions=misconceptions,
    )


def fill_gap(
    slug: str,
    title: str,
    prompt: str,
    *,
    template: str,
    answers: list[str],
    seconds: int,
    explanation: str = "",
    case_sensitive: bool = True,
    mode: str = COMPLETE,
    instructions: str = "Type exactly what belongs in the gap (__).",
    misconceptions: tuple[str, ...] = (),
) -> dict:
    template = code(template).rstrip("\n")
    if len(GAP_PATTERN.findall(template)) != 1:
        raise ValueError(f"Fill-gap template {slug!r} must contain exactly one __ gap.")
    spec = {"accepted_answers": answers, "case_sensitive": case_sensitive}
    if explanation:
        spec["explanation"] = explanation
    return _exercise(
        slug,
        title,
        prompt,
        instructions=instructions,
        response_type="fill_gap",
        mode=mode,
        seconds=seconds,
        content={"template": template},
        spec=spec,
        misconceptions=misconceptions,
    )


def code_stdout(
    slug: str,
    title: str,
    prompt: str,
    *,
    mode: str,
    seconds: int,
    starter: str,
    solution: str,
    expected: str | None = None,
    tests: list[tuple[str, str]] | None = None,
    instructions: str = "Your program's printed output is checked.",
    extra_content: dict | None = None,
    misconceptions: tuple[str, ...] = (),
) -> dict:
    """Output-based program. Pass ``expected`` for a single run without input, or
    ``tests`` as (stdin, expected_stdout) pairs."""
    if tests is None:
        tests = [("", expected)]
    return _exercise(
        slug,
        title,
        prompt,
        instructions=instructions,
        response_type="code",
        mode=mode,
        seconds=seconds,
        content={"language": "python", "starter_code": code(starter), **(extra_content or {})},
        spec={
            "strategy": "stdout",
            "tests": [{"stdin": stdin, "expected_stdout": out} for stdin, out in tests],
            "reference_solution": code(solution),
        },
        misconceptions=misconceptions,
    )


def code_function(
    slug: str,
    title: str,
    prompt: str,
    *,
    mode: str,
    seconds: int,
    function_name: str,
    starter: str,
    solution: str,
    tests: list[tuple],
    instructions: str = "",
    same_process: bool = False,
    misconceptions: tuple[str, ...] = (),
) -> dict:
    """Function-based exercise. ``tests`` items are (args, expected) or
    (args, kwargs, expected)."""
    cases = []
    for case in tests:
        args, kwargs, expected = case if len(case) == 3 else (case[0], {}, case[1])
        cases.append({"args": list(args), "kwargs": kwargs, "expected": expected})
    spec = {
        "strategy": "function",
        "function_name": function_name,
        "tests": cases,
        "reference_solution": code(solution),
    }
    if same_process:
        # The bug only shows when the function is called repeatedly in one process.
        spec["run_tests_in_one_process"] = True
    return _exercise(
        slug,
        title,
        prompt,
        instructions=instructions
        or f"Your {function_name}() function is called with several different inputs.",
        response_type="code",
        mode=mode,
        seconds=seconds,
        content={"language": "python", "starter_code": code(starter)},
        spec=spec,
        misconceptions=misconceptions,
    )


def text_rubric(
    slug: str,
    title: str,
    prompt: str,
    *,
    mode: str,
    seconds: int,
    criteria: list[str],
    instructions: str,
    misconceptions: tuple[str, ...] = (),
) -> dict:
    return _exercise(
        slug,
        title,
        prompt,
        instructions=instructions,
        response_type="text",
        mode=mode,
        seconds=seconds,
        content={},
        spec={"strategy": "rubric", "criteria": criteria},
        misconceptions=misconceptions,
    )
