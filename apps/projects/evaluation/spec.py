"""Validation of a project stage's private evaluation spec.

Shape::

    {
        "strategy": "stdout" | "function",
        "function_name": "analyse",                 # function strategy only
        "tests": [
            {"stdin": "", "expected_stdout": "...", "driver": "..."},   # stdout
            {"args": [...], "kwargs": {...}, "expected": ...},           # function
        ],
        "requires": {"functions": [...], "classes": [...], "methods": ["Class.method"],
                     "constructs": ["try", ...]},
        "fixtures": {"data.csv": "..."},
        "run_tests_in_one_process": false,
    }

``driver`` is private code appended after the learner's program; it exercises classes and
functions and prints what is compared. Everything here stays on the server.
"""

from apps.python_runner.fixtures import FixtureRejected, validate_fixture_files

STRATEGIES = ("stdout", "function")
CONSTRUCTS = frozenset(
    {
        "class",
        "comprehension",
        "def",
        "dict",
        "for",
        "if",
        "import",
        "list",
        "main_guard",
        "open",
        "return",
        "try",
        "while",
        "with",
    }
)
REQUIRE_KEYS = ("functions", "classes", "methods", "constructs")
SPEC_KEYS = frozenset(
    {"strategy", "function_name", "tests", "requires", "fixtures", "run_tests_in_one_process"}
)
MAX_TESTS = 30


def _identifier(value: object) -> bool:
    return isinstance(value, str) and value.isidentifier()


def _test_errors(strategy: str, position: int, test: object) -> list[str]:
    label = f"Test {position}"
    if not isinstance(test, dict):
        return [f"{label} must be an object."]
    errors = []
    if strategy == "stdout":
        allowed = {"stdin", "expected_stdout", "driver"}
        for key in ("stdin", "expected_stdout"):
            if not isinstance(test.get(key), str):
                errors.append(f"{label} needs a text '{key}'.")
        if "driver" in test and not isinstance(test["driver"], str):
            errors.append(f"{label} 'driver' must be text.")
    else:
        allowed = {"args", "kwargs", "expected"}
        if not isinstance(test.get("args"), list):
            errors.append(f"{label} needs a list 'args'.")
        if not isinstance(test.get("kwargs"), dict):
            errors.append(f"{label} needs an object 'kwargs'.")
        if "expected" not in test:
            errors.append(f"{label} needs an 'expected' value.")
    unknown = set(test) - allowed
    if unknown:
        errors.append(f"{label} has unknown keys: {', '.join(sorted(unknown))}.")
    return errors


def _requires_errors(requires: object) -> list[str]:
    if not isinstance(requires, dict):
        return ["'requires' must be an object."]
    errors = []
    unknown = set(requires) - set(REQUIRE_KEYS)
    if unknown:
        errors.append(f"'requires' has unknown keys: {', '.join(sorted(unknown))}.")
    for key in REQUIRE_KEYS:
        values = requires.get(key, [])
        if not isinstance(values, list):
            errors.append(f"'requires.{key}' must be a list.")
            continue
        for value in values:
            if key == "constructs":
                ok = value in CONSTRUCTS
            elif key == "methods":
                parts = value.split(".") if isinstance(value, str) else []
                ok = len(parts) == 2 and all(_identifier(part) for part in parts)
            else:
                ok = _identifier(value)
            if not ok:
                errors.append(f"'requires.{key}' has an invalid entry: {value!r}.")
    return errors


def stage_spec_errors(spec: object) -> list[str]:
    """Every problem with ``spec``; an empty list means it is usable."""
    if not isinstance(spec, dict):
        return ["The evaluation spec must be an object."]
    errors = []
    unknown = set(spec) - SPEC_KEYS
    if unknown:
        errors.append(f"Unknown keys: {', '.join(sorted(unknown))}.")
    strategy = spec.get("strategy")
    if strategy not in STRATEGIES:
        return [*errors, f"'strategy' must be one of: {', '.join(STRATEGIES)}."]
    if strategy == "function" and not _identifier(spec.get("function_name")):
        errors.append("The function strategy needs a valid 'function_name'.")
    tests = spec.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append("'tests' must be a non-empty list.")
    elif len(tests) > MAX_TESTS:
        errors.append(f"At most {MAX_TESTS} tests are allowed.")
    else:
        for position, test in enumerate(tests, start=1):
            errors.extend(_test_errors(strategy, position, test))
    if "requires" in spec:
        errors.extend(_requires_errors(spec["requires"]))
    if "fixtures" in spec:
        try:
            validate_fixture_files(spec["fixtures"])
        except FixtureRejected as exc:
            errors.append(str(exc))
    if not isinstance(spec.get("run_tests_in_one_process", False), bool):
        errors.append("'run_tests_in_one_process' must be true or false.")
    return errors
