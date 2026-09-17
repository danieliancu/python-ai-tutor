"""Opt-in: every seeded project stage checked through the real Docker sandbox.

Run with ``PYTHON_RUNNER_INTEGRATION=1 python manage.py test apps.projects.tests``.
"""

import os
import unittest
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.evaluation.results import EvaluationStatus
from apps.projects.data.python_foundations_solutions import SOLUTIONS
from apps.projects.evaluation.python import PythonProjectEvaluator
from apps.projects.models import ProjectStage
from apps.python_runner.config import RunnerConfig
from apps.python_runner.docker_backend import docker_available

ENABLED = os.environ.get("PYTHON_RUNNER_INTEGRATION") == "1"
CONFIG = RunnerConfig(
    backend="docker",
    image=os.environ.get("PYTHON_RUNNER_IMAGE") or "python:3.11-slim",
    timeout_seconds=10,
)


@unittest.skipUnless(ENABLED, "Docker integration tests are opt-in (PYTHON_RUNNER_INTEGRATION=1).")
class PythonProjectPackDockerTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        assert docker_available(CONFIG), "Docker is not reachable."

    def setUp(self) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_projects", stdout=StringIO())
        self.evaluator = PythonProjectEvaluator(config_provider=lambda: CONFIG)

    def test_every_stage_is_solvable_and_not_solved_by_its_starter(self) -> None:
        stages = ProjectStage.objects.select_related("project").order_by("project__order", "order")
        self.assertEqual(stages.count(), len(SOLUTIONS))
        previous = {}
        for stage in stages:
            key = (stage.project.slug, stage.slug)
            with self.subTest(stage=key):
                result = self.evaluator.evaluate(stage.evaluation_spec, SOLUTIONS[key])
                self.assertEqual(result.status, EvaluationStatus.CORRECT, dict(result.diagnostics))
                # What the learner starts from (starter code or the previous stage's work)
                # must not already pass.
                start = stage.starter_code or previous.get(stage.project.slug, "")
                if start.strip():
                    before = self.evaluator.evaluate(stage.evaluation_spec, start)
                    self.assertNotEqual(before.status, EvaluationStatus.CORRECT)
                    for value in dict(before.diagnostics).values():
                        self.assertNotIn("\n", value)
            previous[stage.project.slug] = SOLUTIONS[key]

    def test_wrong_output_and_hidden_data_do_not_leak(self) -> None:
        stage = ProjectStage.objects.get(project__slug="expense-tracker", slug="load-the-file")
        wrong = SOLUTIONS[("expense-tracker", "parse-transactions")] + (
            "\n\ndef load_transactions(filename):\n"
            "    with open(filename) as file:\n"
            "        try:\n"
            "            print(file.read())\n"
            "        except ValueError:\n"
            "            pass\n"
            "    return []\n"
        )
        result = self.evaluator.evaluate(stage.evaluation_spec, wrong)
        self.assertEqual(result.status, EvaluationStatus.INCORRECT)
        # The learner's program printed the whole fixture; none of it comes back.
        self.assertLessEqual(set(result.diagnostics), {"reason", "error_type"})
        for text in (result.message, *dict(result.diagnostics).values()):
            self.assertNotIn("2026-01-03", text)
