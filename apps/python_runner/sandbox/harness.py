"""Function-exercise harness. Runs only INSIDE the isolated runner container.

The host copies this file next to ``learner.py`` (both read-only) and runs
``python -I -B /sandbox/harness.py``. The request arrives on stdin and contains only the
function name, the call arguments and a per-run marker: never expected values.

Learner code is loaded as a separate module (never concatenated with this file). Anything it
prints is discarded so it can't corrupt the reply. The reply is one final line on the original
stdout: ``<marker><json envelope>``, reporting only actual results. The host compares them with
the hidden expectations.

This file uses only the standard library and must stay compatible with the runner image.
"""

import importlib.util
import io
import json
import math
import sys

LEARNER_PATH = "/sandbox/learner.py"
MAX_DEPTH = 50

MISSING_FUNCTION = "missing_function"
NOT_CALLABLE = "not_callable"
RUNTIME_ERROR = "runtime_error"
NON_SERIALIZABLE = "non_serializable_result"


class NotSerializable(Exception):
    pass


class DiscardingWriter(io.TextIOBase):
    """Stands in for stdout/stderr while learner code runs."""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        return len(text)


def to_json_value(value: object, depth: int = 0) -> object:
    """Return ``value`` if it is plain JSON data, else raise NotSerializable.

    Only exact built-in types are accepted, so learner subclasses can't customise how a
    value is reported.
    """
    if depth > MAX_DEPTH:
        raise NotSerializable
    kind = type(value)
    if value is None or kind in (bool, int, str):
        return value
    if kind is float:
        if not math.isfinite(value):
            raise NotSerializable
        return value
    if kind in (list, tuple):
        return [to_json_value(item, depth + 1) for item in value]
    if kind is dict:
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                raise NotSerializable
            result[key] = to_json_value(item, depth + 1)
        return result
    raise NotSerializable


def failure(error: str, exc: BaseException | None = None) -> dict:
    reply = {"ok": False, "error": error}
    if exc is not None:
        reply["error_type"] = type(exc).__name__
    return reply


def call_function(module: object, function_name: str, call: dict) -> dict:
    try:
        function = getattr(module, function_name)
    except BaseException:
        return failure(MISSING_FUNCTION)
    if not callable(function):
        return failure(NOT_CALLABLE)
    try:
        value = function(*call["args"], **call["kwargs"])
    except BaseException as exc:
        return failure(RUNTIME_ERROR, exc)
    try:
        return {"ok": True, "value": to_json_value(value)}
    except (NotSerializable, RecursionError):
        return failure(NON_SERIALIZABLE)


def load_learner_module() -> object:
    spec = importlib.util.spec_from_file_location("learner", LEARNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["learner"] = module
    spec.loader.exec_module(module)
    return module


def envelope_line(marker: str, results: list[dict]) -> str:
    return "\n" + marker + json.dumps({"results": results}, allow_nan=False) + "\n"


def main() -> None:
    reply_stream = sys.stdout
    request = json.loads(sys.stdin.read())
    calls = request["calls"]

    sys.stdin = io.StringIO("")
    sys.stdout = sys.stderr = DiscardingWriter()
    try:
        module = load_learner_module()
    except BaseException as exc:
        results = [failure(RUNTIME_ERROR, exc) for _ in calls]
    else:
        results = [call_function(module, request["function_name"], call) for call in calls]

    reply_stream.write(envelope_line(request["marker"], results))
    reply_stream.flush()


if __name__ == "__main__":
    main()
