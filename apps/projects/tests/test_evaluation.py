from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.evaluation.results import EvaluationStatus
from apps.projects.evaluation import UnsupportedProjectEvaluator, evaluator_for
from apps.projects.evaluation.python import ProjectSpecError, PythonProjectEvaluator
from apps.projects.evaluation.spec import stage_spec_errors
from apps.projects.evaluation.structure import check_structure
from apps.projects.models import ProjectConceptRequirement, ProjectStage
from apps.projects.tests.helpers import ProjectFixtures
from apps.python_runner.exceptions import RunnerUnavailableError
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import (
    DISABLED,
    ENABLED,
    FakeBackend,
    function_calls,
    harness_reply,
    outcome,
)

CODE = "def total(items):\n    return sum(items)\n"
FIXTURES = {"data.csv": "a,b\nPRIVATE-ROW\n"}


def evaluator(handler, config=ENABLED):
    backend = FakeBackend(handler)
    return (
        PythonProjectEvaluator(
            config_provider=lambda: config,
            runner_factory=lambda cfg: PythonRunner(cfg, backend),
        ),
        backend,
    )


def function_spec(*tests, **extra):
    return {
        "strategy": "function",
        "function_name": "total",
        "tests": [{"args": args, "kwargs": {}, "expected": expected} for args, expected in tests],
        **extra,
    }


def marker_of(files):
    line = next(line for line in files["learner.py"].splitlines() if "@@CHECK-" in line)
    return line.split("'")[1]


class PythonProjectEvaluatorTests(SimpleTestCase):
    def test_function_results(self) -> None:
        def handler(files, argv, stdin):
            return harness_reply(
                stdin,
                [{"ok": True, "value": sum(call["args"][0])} for call in function_calls(stdin)],
            )

        check, backend = evaluator(handler)
        spec = function_spec(([[1, 2]], 3), ([[]], 0), fixtures=FIXTURES)
        self.assertEqual(check.evaluate(spec, CODE).status, EvaluationStatus.CORRECT)
        self.assertEqual(len(backend.requests), 2)
        self.assertEqual(backend.requests[0]["files"]["fixtures/data.csv"], FIXTURES["data.csv"])
        wrong = check.evaluate(function_spec(([[1, 2]], 4)), CODE)
        self.assertEqual(
            (wrong.status, dict(wrong.diagnostics)),
            (EvaluationStatus.INCORRECT, {"reason": "wrong_result"}),
        )

    def test_learner_failures(self) -> None:
        cases = {
            "runtime_error": (
                lambda f, a, s: harness_reply(
                    s, [{"ok": False, "error": "runtime_error", "error_type": "KeyError"}]
                ),
                {"reason": "runtime_error", "error_type": "KeyError"},
            ),
            "timeout": (lambda f, a, s: outcome(timed_out=True), {"reason": "timeout"}),
            "output_limit": (
                lambda f, a, s: outcome(output_limited=True),
                {"reason": "output_limit"},
            ),
        }
        for name, (handler, diagnostics) in cases.items():
            with self.subTest(name=name):
                result = evaluator(handler)[0].evaluate(function_spec(([[1]], 1)), CODE)
                self.assertEqual(result.status, EvaluationStatus.INCORRECT)
                self.assertEqual(dict(result.diagnostics), diagnostics)

    def test_stdout_with_driver_compares_only_the_driver_output(self) -> None:
        def handler(files, argv, stdin):
            marker = marker_of(files)
            return outcome(stdout=f"learner print\n{marker}\nfrom driver\n")

        check, backend = evaluator(handler)
        spec = {
            "strategy": "stdout",
            "tests": [{"stdin": "", "driver": "print('x')", "expected_stdout": "from driver\n"}],
            "fixtures": FIXTURES,
        }
        self.assertEqual(check.evaluate(spec, CODE).status, EvaluationStatus.CORRECT)
        program = backend.requests[0]["files"]["learner.py"]
        self.assertTrue(program.startswith(CODE.rstrip()))
        self.assertTrue(program.endswith("print('x')"))
        self.assertEqual(backend.requests[0]["argv"][0], "/sandbox/bootstrap.py")

        spec["tests"][0]["expected_stdout"] = "something else\n"
        result = check.evaluate(spec, CODE)
        self.assertEqual(dict(result.diagnostics), {"reason": "output_mismatch"})
        for value in [result.message, *dict(result.diagnostics).values()]:
            self.assertNotIn("PRIVATE-ROW", value)
            self.assertNotIn("from driver", value)

    def test_a_program_that_exits_before_the_driver_fails(self) -> None:
        check, _ = evaluator(lambda f, a, s: outcome(stdout="only learner output\n"))
        spec = {
            "strategy": "stdout",
            "tests": [{"stdin": "", "driver": "print(1)", "expected_stdout": "1\n"}],
        }
        result = check.evaluate(spec, CODE)
        self.assertEqual(dict(result.diagnostics), {"reason": "output_mismatch"})

    def test_plain_stdout_and_runtime_errors(self) -> None:
        spec = {"strategy": "stdout", "tests": [{"stdin": "2\n", "expected_stdout": "4\n"}]}
        check, backend = evaluator(lambda f, a, s: outcome(stdout="4\r\n"))
        self.assertEqual(check.evaluate(spec, CODE).status, EvaluationStatus.CORRECT)
        self.assertEqual(backend.requests[0]["stdin"], "2\n")
        crash = evaluator(
            lambda f, a, s: outcome(stderr="Traceback...\nZeroDivisionError: boom\n", exit_code=1)
        )[0].evaluate(spec, CODE)
        self.assertEqual(
            dict(crash.diagnostics), {"reason": "runtime_error", "error_type": "ZeroDivisionError"}
        )

    def test_invalid_source_and_structure_never_run(self) -> None:
        check, backend = evaluator(lambda *a: outcome())
        spec = function_spec(([[1]], 1), requires={"functions": ["total"], "constructs": ["for"]})
        self.assertEqual(check.evaluate(spec, "").status, EvaluationStatus.INVALID)
        self.assertEqual(check.evaluate(spec, 42).status, EvaluationStatus.INVALID)
        result = check.evaluate(spec, CODE)
        self.assertEqual(
            dict(result.diagnostics), {"reason": "missing_construct", "missing": "for"}
        )
        self.assertEqual(backend.requests, [])

    def test_disabled_and_unavailable_runner(self) -> None:
        disabled, backend = evaluator(lambda *a: outcome(), config=DISABLED)
        result = disabled.evaluate(function_spec(([[1]], 1)), CODE)
        self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
        self.assertEqual(backend.requests, [])

        def down(*args):
            raise RunnerUnavailableError("daemon down")

        with self.assertRaises(RunnerUnavailableError):
            evaluator(down)[0].evaluate(function_spec(([[1]], 1)), CODE)

    def test_a_broken_spec_is_never_blamed_on_the_learner(self) -> None:
        with self.assertRaises(ProjectSpecError):
            evaluator(lambda *a: outcome())[0].evaluate({"strategy": "magic"}, CODE)

    def test_other_domains_are_unsupported(self) -> None:
        self.assertIsInstance(evaluator_for("english"), UnsupportedProjectEvaluator)
        result = evaluator_for("english").evaluate({}, "hello")
        self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
        self.assertIsInstance(evaluator_for("python"), PythonProjectEvaluator)


class StructureTests(SimpleTestCase):
    SOURCE = (
        "import json\n\n"
        "class Shop:\n    def add(self, item):\n        try:\n            pass\n"
        "        except ValueError:\n            pass\n\n"
        "def load(name):\n    with open(name) as f:\n        return [x for x in f]\n\n"
        "if __name__ == '__main__':\n    load('x')\n"
    )

    def test_requirements_are_found_without_running_code(self) -> None:
        requires = {
            "functions": ["load"],
            "classes": ["Shop"],
            "methods": ["Shop.add"],
            "constructs": ["import", "try", "with", "open", "comprehension", "main_guard"],
        }
        self.assertIsNone(check_structure(self.SOURCE, requires))

    def test_missing_pieces(self) -> None:
        cases = [
            ({"functions": ["save"]}, ("missing_function", "save")),
            ({"functions": ["add"]}, ("missing_function", "add")),  # methods aren't functions
            ({"classes": ["Cart"]}, ("missing_class", "Cart")),
            ({"methods": ["Shop.remove"]}, ("missing_method", "Shop.remove")),
            ({"constructs": ["while"]}, ("missing_construct", "while")),
        ]
        for requires, expected in cases:
            with self.subTest(requires=requires):
                problem = check_structure(self.SOURCE, requires)
                self.assertEqual((problem.reason, problem.missing), expected)
        self.assertEqual(check_structure("def (:", {}).reason, "syntax_error")
        guarded = "def main(): pass\nif __name__ != '__main__':\n    main()\n"
        self.assertEqual(
            check_structure(guarded, {"constructs": ["main_guard"]}).missing, "main_guard"
        )

    def test_spec_validation(self) -> None:
        self.assertEqual(stage_spec_errors(function_spec(([[1]], 1))), [])
        bad = [
            None,
            {"strategy": "stdout", "tests": []},
            {"strategy": "stdout", "tests": [{"stdin": "", "expected_stdout": 1}]},
            {"strategy": "function", "tests": [{"args": [], "kwargs": {}, "expected": 1}]},
            function_spec(([[1]], 1), requires={"constructs": ["goto"]}),
            function_spec(([[1]], 1), requires={"methods": ["nodot"]}),
            function_spec(([[1]], 1), fixtures={"../x": "y"}),
            function_spec(([[1]], 1), reference_solution="print(1)"),
            function_spec(([[1]], 1), run_tests_in_one_process="yes"),
        ]
        for spec in bad:
            with self.subTest(spec=spec):
                self.assertTrue(stage_spec_errors(spec))


class ModelValidationTests(ProjectFixtures, TestCase):
    def test_published_stages_need_a_valid_spec(self) -> None:
        stage = self.stages[0]
        stage.evaluation_spec = {"strategy": "stdout", "tests": []}
        with self.assertRaises(ValidationError):
            stage.save()
        stage.is_published = False
        stage.evaluation_spec = {}
        stage.save()
        stage.requirements = "not a list"
        with self.assertRaises(ValidationError):
            stage.save()

    def test_requirements_stay_in_the_projects_world(self) -> None:
        from apps.exercises.tests.helpers import make_lesson_chain

        foreign = make_lesson_chain("Other World").concept
        with self.assertRaises(ValidationError):
            ProjectConceptRequirement.objects.create(project=self.project, concept=foreign)
        with self.assertRaises(ValidationError):
            ProjectConceptRequirement.objects.create(
                project=self.project, concept=self.concept_a, minimum_mastery=101
            )

    def test_stage_order_is_unique_per_project(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectStage.objects.create(
                project=self.project,
                title="Dup",
                slug="dup",
                objective="o",
                instructions="i",
                order=1,
                estimated_minutes=1,
            )
