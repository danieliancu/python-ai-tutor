"""The Python tutor on the real Python Foundations pack (fake provider, no Docker)."""

import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.tests.helpers import ENABLED, keys
from apps.attempts.services import record_attempt
from apps.curriculum.models import World
from apps.evaluation import registry
from apps.evaluation.evaluators.code import CodeEvaluator
from apps.exercises.models import Exercise, ResponseType
from apps.learners.models import Enrollment, LearnerProfile
from apps.python_runner.evaluator import PythonCodeEvaluator
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import ENABLED as RUNNER_ON
from apps.python_runner.tests.fakes import FakeBackend, function_calls, harness_reply, outcome

ANSWER_KEYS = {
    "reference_solution",
    "correct_option",
    "accepted_answers",
    "expected_stdout",
    "tests",
}


@override_settings(AI_TUTOR=ENABLED)
class PythonPackTutorTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def setUp(self) -> None:
        self.user = make_user("learner")
        self.world = World.objects.get(slug="python-foundations")
        self.enrollment = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=self.user), world=self.world
        )
        self.provider = FakeTutorProvider()
        patcher = mock.patch("apps.ai_tutor.services.get_provider", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(self.user)

    def runner(self, handler) -> None:
        python = PythonCodeEvaluator(
            config_provider=lambda: RUNNER_ON,
            runner_factory=lambda config: PythonRunner(config, FakeBackend(handler)),
        )
        patcher = mock.patch.dict(
            registry.EVALUATORS, {ResponseType.CODE: CodeEvaluator({"python": python})}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def exercise(self, slug: str) -> Exercise:
        return Exercise.objects.get(lesson__concept__skill__world=self.world, slug=slug)

    def ask(self, intent: str, exercise: Exercise, message: str = ""):
        response = self.client.post(
            reverse("ai_tutor:turns", args=[self.world.pk]),
            data=json.dumps({"intent": intent, "exercise_id": exercise.pk, "message": message}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json(), self.provider.requests[-1]

    def assert_no_answers(self, request, exercise) -> None:
        spec = exercise.evaluation_spec
        self.assertEqual(keys(request.server_context) & ANSWER_KEYS, set())
        text = json.dumps(request.server_context, default=str) + request.instructions
        for secret in (spec.get("reference_solution"), spec.get("correct_option")):
            if secret and len(secret) > 3:
                self.assertNotIn(secret, text)
        for answer in spec.get("accepted_answers", []):
            self.assertNotIn(
                json.dumps(answer), json.dumps(request.server_context.get("private_teaching"))
            )
        for test in spec.get("tests", []):
            if "expected_stdout" in test:
                self.assertNotIn(json.dumps(test["expected_stdout"]), text)

    def ladder(self, exercise, expected=("hint", "strong_hint", "explanation", "solution")):
        kinds = []
        for _ in expected:
            data, request = self.ask("solution", exercise, "Just give me the answer.")
            kinds.append(data["response_kind"])
            if data["response_kind"] != "solution":
                self.assert_no_answers(request, exercise)
        self.assertEqual(kinds, list(expected))
        return request

    def test_function_exercise_with_wrong_result(self) -> None:
        exercise = self.exercise("count-up-off-by-one")
        self.runner(
            lambda files, argv, stdin: harness_reply(
                stdin, [{"ok": True, "value": []} for _ in function_calls(stdin)]
            )
        )
        attempt = record_attempt(
            user=self.user, exercise=exercise, answer=exercise.content["starter_code"]
        )
        self.assertEqual(attempt.status, "incorrect")
        data, request = self.ask("hint", exercise)
        private = request.server_context["private_teaching"]
        self.assertEqual(private["evaluation"]["category"], "wrong_result")
        self.assertTrue(private["source_analysis"]["has_range"])
        self.assertIn("off-by-one", private["teaching_focus"]["watch_misconceptions"])
        self.assert_no_answers(request, exercise)
        # The first hint was already given, so the ladder continues from there.
        solution = self.ladder(exercise, ("strong_hint", "explanation", "solution"))
        self.assertEqual(
            solution.server_context["private_teaching"]["solution_material"],
            {"reference_solution": exercise.evaluation_spec["reference_solution"]},
        )

    def test_fill_gap_and_choice_exercises(self) -> None:
        gap = self.exercise("one-to-five")
        record_attempt(user=self.user, exercise=gap, answer="5")
        solution = self.ladder(gap)
        self.assertEqual(
            solution.server_context["private_teaching"]["solution_material"],
            {"accepted_answers": ["6"]},
        )
        choice = self.exercise("ten-or-more")
        solution = self.ladder(choice)
        material = solution.server_context["private_teaching"]["solution_material"]
        self.assertEqual(material["correct_option"], "b")

    def test_indentation_and_step_exercises(self) -> None:
        self.runner(
            lambda *a: outcome(stderr="IndentationError: expected an indented block\n", exit_code=1)
        )
        branch = self.exercise("indent-the-branch")
        record_attempt(user=self.user, exercise=branch, answer=branch.content["starter_code"])
        _, request = self.ask("hint", branch)
        evaluation = request.server_context["private_teaching"]["evaluation"]
        self.assertEqual(
            (evaluation["category"], evaluation["error_type"]), ("syntax_error", "IndentationError")
        )
        self.assertIn("learning mode is fix", request.instructions)
        self.assert_no_answers(request, branch)

        step = self.exercise("countdown-step")
        _, request = self.ask("explain", step)
        self.assertIsNone(request.server_context["private_teaching"]["evaluation"])
        self.assert_no_answers(request, step)

    def test_print_vs_return_guidance(self) -> None:
        exercise = self.exercise("print-is-not-return")
        data, request = self.ask("ask", exercise, "Why doesn't print give the value back?")
        self.assertEqual(data["response_kind"], "guidance")
        self.assertIn("print vs return", request.instructions)
        self.assertIn("learning mode is recognise", request.instructions)
        self.assert_no_answers(request, exercise)
