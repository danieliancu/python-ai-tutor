import json
from pathlib import Path
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase

from apps.accounts.tests.helpers import make_user
from apps.evaluation import registry
from apps.evaluation.engine import evaluate_exercise, evaluate_for_learner
from apps.evaluation.evaluators.code import CodeEvaluator
from apps.evaluation.exceptions import EvaluationConfigurationError, EvaluationUnavailable
from apps.evaluation.presentation import evaluation_result_presentation
from apps.evaluation.results import EvaluationStatus
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, LearnerProfile
from apps.python_runner.evaluator import PythonCodeEvaluator
from apps.python_runner.exceptions import RunnerUnavailableError
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import (
    DISABLED,
    ENABLED,
    FakeBackend,
    code_exercise,
    function_calls,
    function_spec,
    harness_reply,
    outcome,
    stdout_spec,
)

SOURCE = "print('learner code')\n"


def evaluator_with(handler, config=ENABLED):
    backend = FakeBackend(handler)
    evaluator = PythonCodeEvaluator(
        config_provider=lambda: config,
        runner_factory=lambda cfg: PythonRunner(cfg, backend),
    )
    return evaluator, backend


def fixed_stdout(*outputs):
    """A backend handler returning each output in turn (as stdout)."""
    remaining = list(outputs)
    return lambda files, argv, stdin: remaining.pop(0)


def function_handler(implementation):
    """Answer harness requests by applying ``implementation(args, kwargs)`` to each call.

    ``implementation`` is trusted test code standing in for what the container would report.
    """

    def handler(files, argv, stdin):
        return harness_reply(
            stdin, [implementation(call["args"], call["kwargs"]) for call in function_calls(stdin)]
        )

    return handler


class StdoutStrategyTests(SimpleTestCase):
    spec = stdout_spec(("", "12\n15\n"), ("3\n", "done\n"))

    def evaluate(self, *outcomes):
        evaluator, backend = evaluator_with(fixed_stdout(*outcomes))
        return evaluator.evaluate(code_exercise(self.spec), SOURCE), backend

    def test_all_tests_pass(self) -> None:
        result, backend = self.evaluate(outcome("12\n15\n"), outcome("done\n"))
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        self.assertEqual(
            (result.score, result.is_correct, result.evaluator), (1.0, True, "python_code")
        )
        self.assertEqual([r["stdin"] for r in backend.requests], ["", "3\n"])

    def test_windows_line_endings_are_normalised_but_whitespace_is_not(self) -> None:
        result, _ = self.evaluate(outcome("12\r\n15\r"), outcome("done\n"))
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        for output in ("12\n15", "12 \n15\n", " 12\n15\n", "12\n15\n\n"):
            with self.subTest(output=output):
                result, _ = self.evaluate(outcome(output), outcome("done\n"))
                self.assertEqual(result.status, EvaluationStatus.INCORRECT)
                self.assertEqual(result.diagnostics["reason"], "output_mismatch")

    def test_stops_at_the_first_failing_test(self) -> None:
        result, backend = self.evaluate(outcome("wrong\n"), outcome("done\n"))
        self.assertEqual(result.diagnostics["reason"], "output_mismatch")
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(result.message, "That code didn't pass the checks yet.")

    def test_learner_failures_are_incorrect(self) -> None:
        cases = [
            (outcome(stderr="Traceback\nNameError: x", exit_code=1), "runtime_error", "NameError"),
            (
                outcome(stderr="  File x\nSyntaxError: bad", exit_code=1),
                "runtime_error",
                "SyntaxError",
            ),
            (outcome(exit_code=124, timed_out=True), "timeout", None),
            (outcome("x", exit_code=137, output_limited=True), "output_limit", None),
        ]
        for run, reason, error_type in cases:
            with self.subTest(reason=reason):
                result, _ = self.evaluate(run)
                self.assertEqual(result.status, EvaluationStatus.INCORRECT)
                self.assertEqual((result.score, result.is_correct), (0.0, False))
                self.assertEqual(result.diagnostics["reason"], reason)
                self.assertEqual(result.diagnostics.get("error_type"), error_type)

    def test_infrastructure_failure_is_never_incorrect(self) -> None:
        def broken(*args):
            raise RunnerUnavailableError("daemon down")

        evaluator, _ = evaluator_with(broken)
        with self.assertRaises(RunnerUnavailableError):
            evaluator.evaluate(code_exercise(self.spec), SOURCE)


class FunctionStrategyTests(SimpleTestCase):
    spec = function_spec(
        "is_even",
        ([2], {}, True),
        ([7], {}, False),
        ([], {"n": 0}, True),
        ([-4], {}, True),
    )

    def evaluate(self, implementation, spec=None):
        evaluator, backend = evaluator_with(function_handler(implementation))
        return evaluator.evaluate(code_exercise(spec or self.spec), SOURCE), backend

    @staticmethod
    def is_even(args, kwargs):
        n = args[0] if args else kwargs["n"]
        return {"ok": True, "value": n % 2 == 0}

    def test_correct(self) -> None:
        result, backend = self.evaluate(self.is_even)
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        self.assertEqual(len(backend.requests), 4, "a fresh container per test")
        self.assertEqual(
            [function_calls(r["stdin"]) for r in backend.requests],
            [
                [{"args": [2], "kwargs": {}}],
                [{"args": [7], "kwargs": {}}],
                [{"args": [], "kwargs": {"n": 0}}],
                [{"args": [-4], "kwargs": {}}],
            ],
        )

    def test_wrong_result(self) -> None:
        result, backend = self.evaluate(lambda args, kwargs: {"ok": True, "value": True})
        self.assertEqual(result.status, EvaluationStatus.INCORRECT)
        self.assertEqual(result.diagnostics["reason"], "wrong_result")
        self.assertEqual(len(backend.requests), 2)

    def test_true_is_not_one(self) -> None:
        spec = function_spec("count", ([], {}, 1))
        result, _ = self.evaluate(lambda a, k: {"ok": True, "value": True}, spec)
        self.assertEqual(result.diagnostics["reason"], "wrong_result")
        result, _ = self.evaluate(lambda a, k: {"ok": True, "value": 1.0}, spec)
        self.assertEqual(result.status, EvaluationStatus.CORRECT)

    def test_structured_results(self) -> None:
        spec = function_spec("summary", ([], {}, {"count": 2, "items": [1, None]}))
        result, _ = self.evaluate(
            lambda a, k: {"ok": True, "value": {"items": [1, None], "count": 2.0}}, spec
        )
        self.assertEqual(result.status, EvaluationStatus.CORRECT)
        result, _ = self.evaluate(
            lambda a, k: {"ok": True, "value": {"items": [None, 1], "count": 2}}, spec
        )
        self.assertEqual(result.diagnostics["reason"], "wrong_result")

    def test_error_reasons(self) -> None:
        for reply, reason, error_type in (
            ({"ok": False, "error": "missing_function"}, "missing_function", None),
            ({"ok": False, "error": "not_callable"}, "not_callable", None),
            (
                {"ok": False, "error": "runtime_error", "error_type": "TypeError"},
                "runtime_error",
                "TypeError",
            ),
            ({"ok": False, "error": "non_serializable_result"}, "non_serializable_result", None),
            ({"ok": False, "error": "bogus"}, "invalid_result", None),
        ):
            with self.subTest(reason=reason):
                result, _ = self.evaluate(lambda a, k, r=reply: r)
                self.assertEqual(result.status, EvaluationStatus.INCORRECT)
                self.assertEqual(result.diagnostics["reason"], reason)
                self.assertEqual(result.diagnostics.get("error_type"), error_type)

    def test_timeout_and_output_limit(self) -> None:
        for flags, reason in (
            ({"timed_out": True}, "timeout"),
            ({"output_limited": True}, "output_limit"),
        ):
            evaluator, _ = evaluator_with(lambda *a, f=flags: outcome(exit_code=137, **f))
            with self.subTest(reason=reason):
                result = evaluator.evaluate(code_exercise(self.spec), SOURCE)
                self.assertEqual(result.diagnostics["reason"], reason)

    def test_one_process_mode_sends_all_calls_together(self) -> None:
        spec = function_spec(
            "add_tag",
            (["a"], {}, ["a"]),
            (["b"], {}, ["b"]),
            (["c", ["x"]], {}, ["x", "c"]),
            run_tests_in_one_process=True,
        )
        shared: list = []

        def buggy(args, kwargs):  # models a mutable default shared across calls
            target = args[1] if len(args) > 1 else shared
            target.append(args[0])
            return {"ok": True, "value": list(target)}

        result, backend = self.evaluate(buggy, spec)
        self.assertEqual(len(backend.requests), 1)
        self.assertEqual(len(function_calls(backend.requests[0]["stdin"])), 3)
        self.assertEqual(result.diagnostics["reason"], "wrong_result")

        def fixed(args, kwargs):
            target = list(args[1]) if len(args) > 1 else []
            return {"ok": True, "value": [*target, args[0]]}

        result, _ = self.evaluate(fixed, spec)
        self.assertEqual(result.status, EvaluationStatus.CORRECT)


class EvaluatorGuardTests(SimpleTestCase):
    def test_disabled_runner_is_unsupported_and_runs_nothing(self) -> None:
        evaluator, backend = evaluator_with(lambda *a: outcome(), config=DISABLED)
        result = evaluator.evaluate(code_exercise(stdout_spec(("", "x"))), SOURCE)
        self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
        self.assertEqual(result.message, "Code evaluation is not available yet.")
        self.assertEqual(backend.requests, [])

    def test_invalid_source_is_invalid_and_runs_nothing(self) -> None:
        evaluator, backend = evaluator_with(lambda *a: outcome())
        for answer, reason in (
            (None, "invalid_answer_type"),
            ("  ", "empty_answer"),
            ("a\x00", "invalid_source"),
        ):
            with self.subTest(reason=reason):
                result = evaluator.evaluate(code_exercise(stdout_spec(("", "x"))), answer)
                self.assertEqual(result.status, EvaluationStatus.INVALID)
                self.assertEqual(result.diagnostics["reason"], reason)
        self.assertEqual(backend.requests, [])

    def test_misconfigured_specs_are_configuration_errors(self) -> None:
        evaluator, backend = evaluator_with(lambda *a: outcome())
        for spec in (
            {},
            {"strategy": "shell", "tests": [{"stdin": "", "expected_stdout": ""}]},
            {"strategy": "stdout", "tests": []},
            {"strategy": "function", "tests": [{"args": [], "kwargs": {}, "expected": 1}]},
            {"strategy": "function", "function_name": "f", "tests": [{"args": []}]},
        ):
            with self.subTest(spec=spec), self.assertRaises(EvaluationConfigurationError):
                evaluator.evaluate(code_exercise(spec), SOURCE)
        self.assertEqual(backend.requests, [])


class CodeDispatchTests(SimpleTestCase):
    def test_registry_routes_python_code_to_the_runner_evaluator(self) -> None:
        code = registry.get_evaluator(ResponseType.CODE)
        self.assertIsInstance(code, CodeEvaluator)
        self.assertIsInstance(code.language_evaluators["python"], PythonCodeEvaluator)
        self.assertEqual(set(code.language_evaluators), {"python"})

    def test_python_code_is_evaluated_through_the_engine(self) -> None:
        python, _ = evaluator_with(fixed_stdout(outcome("hi\n")))
        with mock.patch.dict(
            registry.EVALUATORS, {ResponseType.CODE: CodeEvaluator({"python": python})}
        ):
            result = evaluate_exercise(code_exercise(stdout_spec(("", "hi\n"))), SOURCE)
        self.assertEqual(
            (result.status, result.evaluator), (EvaluationStatus.CORRECT, "python_code")
        )

    def test_other_languages_are_unsupported(self) -> None:
        python, backend = evaluator_with(fixed_stdout(outcome("hi\n")))
        code = CodeEvaluator({"python": python})
        for language in ("javascript", "Python", "", None):
            exercise = code_exercise(stdout_spec(("", "hi\n")), language=language)
            with self.subTest(language=language):
                result = code.evaluate(exercise, SOURCE)
                self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
                self.assertEqual(result.evaluator, "code")
                self.assertIsNone(result.is_correct)
        self.assertEqual(backend.requests, [])


class LearnerFacingUnavailableTests(TestCase):
    def setUp(self) -> None:
        lesson = make_lesson_chain("Python Foundations")
        self.exercise = make_exercise(
            lesson,
            response_type=ResponseType.CODE,
            learning_mode=LearningMode.CREATE,
            content={"language": "python", "starter_code": ""},
            evaluation_spec=stdout_spec(("", "hi\n")),
        )
        self.user = make_user("coder")
        profile = LearnerProfile.objects.create(user=self.user)
        Enrollment.objects.create(learner=profile, world=lesson.concept.skill.world)

    def use_evaluator(self, handler):
        python, backend = evaluator_with(handler)
        patcher = mock.patch.dict(
            registry.EVALUATORS, {ResponseType.CODE: CodeEvaluator({"python": python})}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return backend

    def test_runner_failure_becomes_a_safe_unavailable_error(self) -> None:
        def down(*args):
            raise RunnerUnavailableError("docker: Cannot connect to the Docker daemon at unix:///x")

        self.use_evaluator(down)
        with (
            self.assertLogs("apps.evaluation.engine", level="ERROR"),
            self.assertRaises(EvaluationUnavailable) as ctx,
        ):
            evaluate_for_learner(self.user, self.exercise, SOURCE)
        self.assertEqual(str(ctx.exception), "This exercise can't be checked right now.")

    def test_learner_gets_a_clean_result(self) -> None:
        self.use_evaluator(fixed_stdout(outcome("hi\n")))
        self.assertEqual(
            evaluate_for_learner(self.user, self.exercise, SOURCE),
            {"status": "correct", "score": 1.0, "is_correct": True, "message": "Correct."},
        )

    def test_access_is_checked_before_running_anything(self) -> None:
        backend = self.use_evaluator(fixed_stdout(outcome("hi\n")))
        with self.assertRaises(PermissionDenied):
            evaluate_for_learner(make_user("outsider"), self.exercise, SOURCE)
        self.assertEqual(backend.requests, [])


class SecurityTests(SimpleTestCase):
    SECRETS = ("SECRET-EXPECTED-OUT", "SECRET-SOLUTION", "SECRET-RETURN-VALUE")

    def stdout_exercise(self):
        return code_exercise(
            stdout_spec(
                ("in-1\n", "SECRET-EXPECTED-OUT\n"), reference_solution="print('SECRET-SOLUTION')"
            )
        )

    def function_exercise(self):
        return code_exercise(
            function_spec(
                "f",
                (["arg-1"], {"k": "kw-1"}, "SECRET-RETURN-VALUE"),
                reference_solution="def f(*a, **k):\n    return 'SECRET-SOLUTION'\n",
            )
        )

    def test_containers_never_receive_hidden_data(self) -> None:
        for exercise, handler in (
            (self.stdout_exercise(), fixed_stdout(outcome("nope\n"))),
            (self.function_exercise(), function_handler(lambda a, k: {"ok": True, "value": "x"})),
        ):
            evaluator, backend = evaluator_with(handler)
            evaluator.evaluate(exercise, SOURCE)
            # Everything sent to containers except the application's own harness file.
            sent = json.dumps(
                [
                    {
                        **request,
                        "files": {k: v for k, v in request["files"].items() if k != "harness.py"},
                    }
                    for request in backend.requests
                ]
            )
            with self.subTest(strategy=exercise.evaluation_spec["strategy"]):
                for secret in (*self.SECRETS, "reference_solution", "expected", "evaluation_spec"):
                    self.assertNotIn(secret, sent)
                self.assertTrue(backend.requests)
                self.assertEqual(backend.requests[0]["files"]["learner.py"], SOURCE)

    def test_learner_facing_result_reveals_nothing_internal(self) -> None:
        results = []
        for exercise, handler in (
            (self.stdout_exercise(), fixed_stdout(outcome("nope\n"))),
            (
                self.stdout_exercise(),
                fixed_stdout(outcome(stderr='File "/sandbox/learner.py"\nOSError: x', exit_code=1)),
            ),
            (self.stdout_exercise(), fixed_stdout(outcome("SECRET-EXPECTED-OUT\n"))),
            (self.function_exercise(), function_handler(lambda a, k: {"ok": True, "value": "x"})),
        ):
            evaluator, _ = evaluator_with(handler)
            results.append(evaluator.evaluate(exercise, SOURCE))

        forbidden = (
            *self.SECRETS,
            "reference_solution",
            "expected",
            "tests",
            "arg-1",
            "kw-1",
            "in-1",
            "evaluation_spec",
            "docker",
            "pyrun-",
            "/sandbox",
            "/tmp",
            "\\",
        )
        for result in results:
            payload = json.dumps(evaluation_result_presentation(result))
            internal = repr(result)
            with self.subTest(result=result.status):
                for word in forbidden:
                    self.assertNotIn(word, payload)
                    self.assertNotIn(word, internal)


class StaticSafetyTests(SimpleTestCase):
    def test_runner_code_never_executes_locally(self) -> None:
        package = Path(__file__).resolve().parent.parent
        for path in package.rglob("*.py"):
            if "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                for word in ("shell=True", "os.system", "exec(", "eval(", "pickle", "os.popen"):
                    self.assertNotIn(word, source)
                if path.name != "docker_backend.py":
                    # Only the Docker backend may start processes (the docker CLI).
                    self.assertNotIn("subprocess", source)
