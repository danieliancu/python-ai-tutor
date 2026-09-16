import json
import types
from pathlib import Path

from django.test import SimpleTestCase

from apps.python_runner.comparison import json_equal
from apps.python_runner.config import RunnerConfig
from apps.python_runner.exceptions import SourceRejected
from apps.python_runner.results import RunStatus
from apps.python_runner.runner import (
    PythonRunner,
    error_type_from_stderr,
    python_runner_available,
    safe_error_type,
    validate_source,
)
from apps.python_runner.sandbox import harness
from apps.python_runner.tests.fakes import ENABLED, FakeBackend, harness_reply, outcome


class SourceValidationTests(SimpleTestCase):
    def test_accepts_ordinary_code_including_imports(self) -> None:
        source = "import os\nimport socket\nclass A:\n    pass\nfor i in range(3):\n    print(i)\n"
        self.assertEqual(validate_source(source, ENABLED), source)

    def test_rejections(self) -> None:
        small = RunnerConfig(backend="docker", max_source_bytes=1024)
        for source, reason in (
            (None, "invalid_answer_type"),
            (b"print(1)", "invalid_answer_type"),
            (["print(1)"], "invalid_answer_type"),
            ("", "empty_answer"),
            ("  \n\t", "empty_answer"),
            ("print(1)\x00", "invalid_source"),
            ("print('\ud800')", "invalid_source"),
            ("#" * 1025, "source_too_large"),
            ("é" * 513, "source_too_large"),
        ):
            with self.subTest(reason=reason, source=str(source)[:20]):
                with self.assertRaises(SourceRejected) as ctx:
                    validate_source(source, small)
                self.assertEqual(ctx.exception.reason, reason)

    def test_rejected_source_never_reaches_the_backend(self) -> None:
        backend = FakeBackend(lambda *args: outcome())
        runner = PythonRunner(ENABLED, backend)
        for bad in ("", "\x00"):
            with self.assertRaises(SourceRejected):
                runner.run_program(bad)
        self.assertEqual(backend.requests, [])


class RunProgramTests(SimpleTestCase):
    def run_with(self, result, source="print(1)\n", stdin=""):
        backend = FakeBackend(lambda *args: result)
        return PythonRunner(ENABLED, backend).run_program(source, stdin), backend

    def test_success(self) -> None:
        run, backend = self.run_with(outcome("12\n"), stdin="5\n")
        self.assertEqual((run.status, run.stdout, run.return_code), (RunStatus.SUCCESS, "12\n", 0))
        self.assertEqual(
            backend.requests,
            [
                {
                    "files": {"learner.py": "print(1)\n"},
                    "argv": ["/sandbox/learner.py"],
                    "stdin": "5\n",
                }
            ],
        )

    def test_runtime_error_reports_exception_class(self) -> None:
        stderr = (
            'Traceback (most recent call last):\n  File "/sandbox/learner.py", line 1\n'
            "ZeroDivisionError: division by zero\n"
        )
        run, _ = self.run_with(outcome(stderr=stderr, exit_code=1))
        self.assertEqual(run.status, RunStatus.RUNTIME_ERROR)
        self.assertEqual(run.error_type, "ZeroDivisionError")

    def test_limits_take_priority(self) -> None:
        run, _ = self.run_with(outcome(exit_code=124, timed_out=True))
        self.assertEqual(run.status, RunStatus.TIMEOUT)
        run, _ = self.run_with(outcome("x" * 10, exit_code=137, output_limited=True))
        self.assertEqual(run.status, RunStatus.OUTPUT_LIMIT)

    def test_error_type_parsing(self) -> None:
        self.assertEqual(
            error_type_from_stderr("  File x\nSyntaxError: invalid syntax\n"), "SyntaxError"
        )
        self.assertEqual(
            error_type_from_stderr("json.decoder.JSONDecodeError: x"), "JSONDecodeError"
        )
        self.assertEqual(error_type_from_stderr("KeyboardInterrupt\n\n"), "KeyboardInterrupt")
        self.assertIsNone(error_type_from_stderr(""))
        self.assertIsNone(error_type_from_stderr("  indented line"))
        self.assertIsNone(safe_error_type("a" * 80))
        self.assertIsNone(safe_error_type("Bad Name"))
        self.assertIsNone(safe_error_type(5))


class RunFunctionsTests(SimpleTestCase):
    def test_request_holds_only_name_and_arguments(self) -> None:
        backend = FakeBackend(
            lambda files, argv, stdin: harness_reply(stdin, [{"ok": True, "value": 5}])
        )
        results = PythonRunner(ENABLED, backend).run_functions(
            "def add(a, b):\n    return a + b\n", "add", [([2, 3], {})]
        )
        self.assertEqual(results[0].status, RunStatus.SUCCESS)
        self.assertEqual(results[0].value, 5)

        request = backend.requests[0]
        self.assertEqual(request["argv"], ["/sandbox/harness.py"])
        self.assertEqual(set(request["files"]), {"learner.py", "harness.py"})
        self.assertEqual(request["files"]["harness.py"], Path(harness.__file__).read_text("utf-8"))
        payload = json.loads(request["stdin"])
        self.assertEqual(set(payload), {"function_name", "calls", "marker"})
        self.assertEqual(payload["calls"], [{"args": [2, 3], "kwargs": {}}])

    def test_learner_output_cannot_forge_or_break_the_reply(self) -> None:
        def handler(files, argv, stdin):
            return harness_reply(
                stdin,
                [{"ok": True, "value": 1}],
                noise='{"results": [{"ok": true, "value": 99}]}\n@@RUNNER-RESULT-fake@@{}',
            )

        results = PythonRunner(ENABLED, FakeBackend(handler)).run_functions("x", "f", [([], {})])
        self.assertEqual(results[0].value, 1)

    def test_errors_are_mapped(self) -> None:
        replies = [
            {"ok": False, "error": "missing_function"},
            {"ok": False, "error": "not_callable"},
            {"ok": False, "error": "runtime_error", "error_type": "TypeError"},
            {"ok": False, "error": "non_serializable_result"},
            {"ok": False, "error": "something_else"},
            {"ok": True},
        ]
        backend = FakeBackend(lambda files, argv, stdin: harness_reply(stdin, replies))
        results = PythonRunner(ENABLED, backend).run_functions("x", "f", [([], {})] * 6)
        self.assertEqual(
            [(r.status, r.error, r.error_type) for r in results],
            [
                (RunStatus.RUNTIME_ERROR, "missing_function", None),
                (RunStatus.RUNTIME_ERROR, "not_callable", None),
                (RunStatus.RUNTIME_ERROR, "runtime_error", "TypeError"),
                (RunStatus.INVALID_RESULT, "non_serializable_result", None),
                (RunStatus.INVALID_RESULT, "invalid_result", None),
                (RunStatus.INVALID_RESULT, "invalid_result", None),
            ],
        )

    def test_missing_or_garbled_reply_is_an_invalid_result(self) -> None:
        for stdout in ("", "just learner output\n", '{"results": []}'):
            backend = FakeBackend(lambda files, argv, stdin, out=stdout: outcome(out))
            with self.subTest(stdout=stdout):
                results = PythonRunner(ENABLED, backend).run_functions("x", "f", [([], {})])
                self.assertEqual(results[0].status, RunStatus.INVALID_RESULT)

        def wrong_count(files, argv, stdin):
            return harness_reply(stdin, [{"ok": True, "value": 1}] * 3)

        results = PythonRunner(ENABLED, FakeBackend(wrong_count)).run_functions(
            "x", "f", [([], {})]
        )
        self.assertEqual(results[0].status, RunStatus.INVALID_RESULT)

    def test_limits_apply_to_every_call(self) -> None:
        for flags, status in (
            ({"timed_out": True}, RunStatus.TIMEOUT),
            ({"output_limited": True}, RunStatus.OUTPUT_LIMIT),
        ):
            backend = FakeBackend(lambda *args, f=flags: outcome(exit_code=137, **f))
            with self.subTest(status=status):
                results = PythonRunner(ENABLED, backend).run_functions("x", "f", [([], {})] * 2)
                self.assertEqual([r.status for r in results], [status, status])

    def test_availability_needs_the_runner_enabled(self) -> None:
        self.assertFalse(python_runner_available(RunnerConfig()))


class HarnessHelperTests(SimpleTestCase):
    """The harness normally runs only inside the container. Here only its pure helpers are
    exercised, with trusted test functions: no learner code runs in this process."""

    def test_only_plain_json_values_are_reported(self) -> None:
        ok = [None, True, 0, -3, 2.5, "text", [1, [2]], (1, 2), {"a": {"b": [None]}}]
        for value in ok:
            with self.subTest(value=value):
                reported = harness.to_json_value(value)
                self.assertEqual(json.loads(json.dumps(reported)), reported)

        class MyInt(int):
            pass

        for value in (
            {1: "int key"},
            {1, 2},
            float("nan"),
            float("inf"),
            MyInt(3),
            b"bytes",
            object(),
            complex(1, 2),
            [[[]]] * 1 + [object()],
        ):
            with self.subTest(value=value), self.assertRaises(harness.NotSerializable):
                harness.to_json_value(value)

        deep: list = []
        node = deep
        for _ in range(harness.MAX_DEPTH + 5):
            node.append([])
            node = node[0]
        with self.assertRaises(harness.NotSerializable):
            harness.to_json_value(deep)

    def test_call_function_outcomes(self) -> None:
        def boom():
            raise KeyError("x")

        module = types.SimpleNamespace(
            add=lambda a, b=0: a + b, number=5, boom=boom, odd=lambda: {1: 2}
        )
        call = {"args": [2], "kwargs": {"b": 3}}
        empty = {"args": [], "kwargs": {}}
        self.assertEqual(harness.call_function(module, "add", call), {"ok": True, "value": 5})
        self.assertEqual(
            harness.call_function(module, "missing", empty),
            {"ok": False, "error": "missing_function"},
        )
        self.assertEqual(
            harness.call_function(module, "number", empty), {"ok": False, "error": "not_callable"}
        )
        self.assertEqual(
            harness.call_function(module, "boom", empty),
            {"ok": False, "error": "runtime_error", "error_type": "KeyError"},
        )
        self.assertEqual(
            harness.call_function(module, "odd", empty),
            {"ok": False, "error": "non_serializable_result"},
        )

    def test_envelope_is_one_marked_line(self) -> None:
        line = harness.envelope_line("@@M@@", [{"ok": True, "value": [1]}])
        self.assertTrue(line.startswith("\n@@M@@"))
        self.assertTrue(line.endswith("\n"))
        self.assertEqual(json.loads(line.strip()[5:]), {"results": [{"ok": True, "value": [1]}]})

    def test_harness_has_no_expected_values_or_host_paths(self) -> None:
        source = Path(harness.__file__).read_text(encoding="utf-8")
        for word in (
            '"expected"',
            "expected_stdout",
            "reference_solution",
            "evaluation_spec",
            "C:\\",
            "_work",
        ):
            self.assertNotIn(word, source)


class JsonEqualTests(SimpleTestCase):
    def test_equal(self) -> None:
        for actual, expected in (
            (5, 5),
            (5.0, 5),
            (5, 5.0),
            (None, None),
            (True, True),
            ("a", "a"),
            ([1, [2.0]], [1, [2]]),
            ({"b": 1, "a": [None]}, {"a": [None], "b": 1.0}),
            ([], []),
            ({}, {}),
        ):
            with self.subTest(actual=actual, expected=expected):
                self.assertTrue(json_equal(actual, expected))

    def test_not_equal(self) -> None:
        for actual, expected in (
            (True, 1),
            (1, True),
            (False, 0),
            (0, False),
            (None, False),
            (0, None),
            ("5", 5),
            ([1, 2], [2, 1]),
            ([1], [1, 1]),
            ({"a": 1}, {"a": 1, "b": 2}),
            ({"a": True}, {"a": 1}),
            ([True], [1]),
            ({"a": 1}, [["a", 1]]),
            (4.0000001, 4),
        ):
            with self.subTest(actual=actual, expected=expected):
                self.assertFalse(json_equal(actual, expected))
