"""Real Docker runs. Opt-in: set PYTHON_RUNNER_INTEGRATION=1 (Docker and the runner image
must be available). The normal test suite skips these."""

import os
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.evaluation.results import EvaluationStatus
from apps.exercises.models import Exercise, ResponseType
from apps.python_runner.config import RunnerConfig
from apps.python_runner.docker_backend import CONTAINER_LABEL
from apps.python_runner.evaluator import PythonCodeEvaluator
from apps.python_runner.results import RunStatus
from apps.python_runner.runner import PythonRunner, python_runner_available
from apps.python_runner.tests.fakes import code_exercise, function_spec, stdout_spec

ENABLED = os.environ.get("PYTHON_RUNNER_INTEGRATION") == "1"
CONFIG = RunnerConfig(
    backend="docker",
    image=os.environ.get("PYTHON_RUNNER_IMAGE") or "python:3.11-slim",
    timeout_seconds=3,
    memory_mb=128,
    cpus=0.5,
    pids_limit=64,
    max_output_bytes=65536,
)

skip_unless_enabled = unittest.skipUnless(
    ENABLED, "Docker integration tests are opt-in (set PYTHON_RUNNER_INTEGRATION=1)."
)


def leftover_containers() -> list[str]:
    completed = subprocess.run(
        [CONFIG.docker_binary, "ps", "-a", "-q", "--filter", f"label={CONTAINER_LABEL}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.split()


def evaluator() -> PythonCodeEvaluator:
    return PythonCodeEvaluator(config_provider=lambda: CONFIG)


@skip_unless_enabled
class DockerRunnerTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not python_runner_available(CONFIG):
            raise AssertionError("PYTHON_RUNNER_INTEGRATION=1 but Docker is not reachable.")
        cls.runner = PythonRunner(CONFIG)

    def tearDown(self) -> None:
        self.assertEqual(leftover_containers(), [], "runner containers must always be removed")

    def run_program(self, source: str, stdin: str = ""):
        return self.runner.run_program(source, stdin)

    def test_stdout_and_stdin(self) -> None:
        result = self.run_program("name = input()\nprint(f'Hello, {name}!')\n", "Ana\n")
        self.assertEqual(result.status, RunStatus.SUCCESS)
        self.assertEqual(result.stdout, "Hello, Ana!\n")

    def test_syntax_and_runtime_errors(self) -> None:
        syntax = self.run_program("print('x'\n")
        self.assertEqual(
            (syntax.status, syntax.error_type), (RunStatus.RUNTIME_ERROR, "SyntaxError")
        )
        runtime = self.run_program("print(1 / 0)\n")
        self.assertEqual(
            (runtime.status, runtime.error_type), (RunStatus.RUNTIME_ERROR, "ZeroDivisionError")
        )

    def test_infinite_loop_times_out(self) -> None:
        self.assertEqual(self.run_program("while True:\n    pass\n").status, RunStatus.TIMEOUT)

    def test_ignoring_sigterm_does_not_escape_the_timeout(self) -> None:
        source = (
            "import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True:\n    pass\n"
        )
        self.assertEqual(self.run_program(source).status, RunStatus.TIMEOUT)

    def test_endless_output_is_cut_off(self) -> None:
        result = self.run_program("while True:\n    print('x' * 1000)\n")
        self.assertEqual(result.status, RunStatus.OUTPUT_LIMIT)
        self.assertLessEqual(len(result.stdout.encode()), CONFIG.max_output_bytes)

    def test_network_is_unavailable(self) -> None:
        source = (
            "import socket\n"
            "for host, port in (('1.1.1.1', 53), ('8.8.8.8', 443), ('host.docker.internal', 80)):\n"
            "    try:\n"
            "        socket.create_connection((host, port), timeout=1).close()\n"
            "        print('CONNECTED', host)\n"
            "    except OSError:\n"
            "        print('blocked')\n"
        )
        result = self.run_program(source)
        self.assertEqual(result.status, RunStatus.SUCCESS)
        self.assertEqual(result.stdout, "blocked\nblocked\nblocked\n")

    def test_filesystem_is_isolated(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as sentinel:
            sentinel.write("HOST-SENTINEL")
        self.addCleanup(os.unlink, sentinel.name)
        source = (
            "import os, pathlib\n"
            f"candidates = [{sentinel.name!r}, {Path(sentinel.name).as_posix()!r}, "
            f"'/sandbox/../' + {Path(sentinel.name).name!r}]\n"
            "print(any(os.path.exists(p) for p in candidates))\n"
            "print(sorted(os.listdir('/sandbox')))\n"
            "print(os.getuid(), os.getcwd())\n"
            "prefixes = ('DJANGO', 'DATABASE', 'PYTHON_RUNNER')\n"
            "print(any(k.startswith(prefixes) for k in os.environ))\n"
            "try:\n"
            "    open('/sandbox/learner.py', 'a')\n"
            "    print('sandbox writable')\n"
            "except OSError:\n"
            "    print('sandbox read-only')\n"
            "try:\n"
            "    open('/etc/evil', 'w')\n"
            "    print('root writable')\n"
            "except OSError:\n"
            "    print('root read-only')\n"
            "pathlib.Path('/tmp/scratch.txt').write_text('ok')\n"
            "print(pathlib.Path('/tmp/scratch.txt').read_text())\n"
        )
        result = self.run_program(source)
        self.assertEqual(result.status, RunStatus.SUCCESS, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "False",
                "['learner.py']",
                "65534 /tmp",
                "False",
                "sandbox read-only",
                "root read-only",
                "ok",
            ],
        )

    def test_process_limit(self) -> None:
        source = (
            "import os\ncount = 0\n"
            "try:\n"
            "    for _ in range(200):\n"
            "        if os.fork() == 0:\n"
            "            import time; time.sleep(5); os._exit(0)\n"
            "        count += 1\n"
            "except OSError:\n"
            "    pass\n"
            "print(count < 200)\n"
        )
        result = self.run_program(source)
        self.assertIn("True", result.stdout)

    def test_memory_limit(self) -> None:
        result = self.run_program("data = bytearray(512 * 1024 * 1024)\nprint('allocated')\n")
        self.assertNotEqual(result.status, RunStatus.SUCCESS)
        self.assertNotIn("allocated", result.stdout)

    def test_function_calls(self) -> None:
        source = (
            "print('noise at import')\n"
            "def describe(x, *, upper=False):\n"
            "    print('noise in call')\n"
            "    return {'items': [x, None], 'upper': upper, 'nested': {'t': (1, 2.5)}}\n"
            "number = 3\n"
        )
        results = self.runner.run_functions(
            source, "describe", [(["a"], {}), (["b"], {"upper": True})]
        )
        self.assertEqual(
            [(r.status, r.value) for r in results],
            [
                (
                    RunStatus.SUCCESS,
                    {"items": ["a", None], "upper": False, "nested": {"t": [1, 2.5]}},
                ),
                (
                    RunStatus.SUCCESS,
                    {"items": ["b", None], "upper": True, "nested": {"t": [1, 2.5]}},
                ),
            ],
        )
        self.assertEqual(
            self.runner.run_function(source, "missing", [], {}).error, "missing_function"
        )
        self.assertEqual(self.runner.run_function(source, "number", [], {}).error, "not_callable")
        bad = self.runner.run_function("def f():\n    return {1, 2}\n", "f", [], {})
        self.assertEqual(bad.error, "non_serializable_result")
        crash = self.runner.run_function("def f():\n    raise KeyError('x')\n", "f", [], {})
        self.assertEqual((crash.error, crash.error_type), ("runtime_error", "KeyError"))

    def test_learner_cannot_forge_the_reply(self) -> None:
        forged = '{"results": [{"ok": true, "value": 42}]}'
        source = (
            "import os, sys\n"
            f"forged = {forged!r}\n"
            "os.write(1, ('\\n@@RUNNER-RESULT-guess@@' + forged + '\\n').encode())\n"
            "sys.__stdout__.write(forged + '\\n')\n"
            "def answer():\n    return 1\n"
        )
        self.assertEqual(self.runner.run_function(source, "answer", [], {}).value, 1)


@skip_unless_enabled
class DockerEvaluatorTests(SimpleTestCase):
    def evaluate(self, spec: dict, source: str):
        return evaluator().evaluate(code_exercise(spec), source)

    def test_stdout_correct_and_mismatch(self) -> None:
        spec = stdout_spec(("3\n", "6\n"), ("10\n", "20\n"))
        self.assertEqual(self.evaluate(spec, "print(int(input()) * 2)\n").status, "correct")
        wrong = self.evaluate(spec, "print(int(input()) + 3)\n")
        self.assertEqual(wrong.diagnostics["reason"], "output_mismatch")

    def test_function_results_and_bool_vs_int(self) -> None:
        spec = function_spec("is_even", ([2], {}, True), ([7], {}, False), ([0], {}, True))
        self.assertEqual(
            self.evaluate(spec, "def is_even(n):\n    return n % 2 == 0\n").status, "correct"
        )
        wrong = self.evaluate(spec, "def is_even(n):\n    return 1 - n % 2\n")
        self.assertEqual(wrong.diagnostics["reason"], "wrong_result")

    def test_one_process_mode_reveals_shared_state(self) -> None:
        spec = function_spec(
            "add_tag",
            (["a"], {}, ["a"]),
            (["b"], {}, ["b"]),
            run_tests_in_one_process=True,
        )
        buggy = "def add_tag(tag, tags=[]):\n    tags.append(tag)\n    return tags\n"
        fixed = (
            "def add_tag(tag, tags=None):\n"
            "    tags = tags or []\n"
            "    tags.append(tag)\n"
            "    return tags\n"
        )
        self.assertEqual(self.evaluate(spec, buggy).diagnostics["reason"], "wrong_result")
        self.assertEqual(self.evaluate(spec, fixed).status, "correct")


@skip_unless_enabled
class PythonPackReferenceSolutionTests(TestCase):
    """Every seeded CODE exercise: its reference solution passes, its starter code doesn't.

    reference_solution is used here only for verification, never for learner submissions.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def test_reference_solutions_pass_and_starters_fail(self) -> None:
        exercises = list(Exercise.objects.filter(response_type=ResponseType.CODE))
        self.assertEqual(len(exercises), 69)
        code = evaluator()
        for exercise in exercises:
            with self.subTest(exercise=exercise.slug):
                solution = exercise.evaluation_spec["reference_solution"]
                result = code.evaluate(exercise, solution)
                self.assertEqual(result.status, EvaluationStatus.CORRECT, dict(result.diagnostics))
                starter = code.evaluate(exercise, exercise.content["starter_code"])
                self.assertIn(
                    starter.status, {EvaluationStatus.INCORRECT, EvaluationStatus.INVALID}
                )
        self.assertEqual(leftover_containers(), [])
