"""Compare a function's actual JSON result with the expected value, on the host."""


def json_equal(actual: object, expected: object) -> bool:
    """Deliberate JSON-style equality.

    Booleans only equal booleans (True is not 1), None only equals None, int and float compare
    numerically (5 == 5.0), strings compare exactly, lists compare in order and dictionaries
    compare by keys and values regardless of order.
    """
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is bool and type(expected) is bool and actual == expected
    if actual is None or expected is None:
        return actual is None and expected is None
    if isinstance(actual, int | float) and isinstance(expected, int | float):
        return actual == expected
    if isinstance(actual, str) or isinstance(expected, str):
        return isinstance(actual, str) and isinstance(expected, str) and actual == expected
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_equal(a, e) for a, e in zip(actual, expected, strict=True)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_equal(actual[key], expected[key]) for key in expected
        )
    return False
