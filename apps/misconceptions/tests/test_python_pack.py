"""The misconception engine on the real Python Foundations pack (Docker-free)."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.attempts.services import record_attempt
from apps.curriculum.models import World
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment
from apps.misconceptions.definitions import all_definitions, is_safe_code
from apps.misconceptions.domains.python.definitions import CATALOG, DEFINITIONS
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.tests.helpers import MisconceptionFixtures
from apps.python_runner.tests.fakes import function_calls, harness_reply, outcome

WORLD_SLUG = "python-foundations"


class PythonCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def test_every_pack_tag_is_safe_and_registered(self) -> None:

        registered = all_definitions()
        exercises = Exercise.objects.filter(lesson__concept__skill__world__slug=WORLD_SLUG)
        tags = set()
        for exercise in exercises:
            codes = exercise.evaluation_spec.get("misconceptions", [])
            self.assertEqual(len(codes), len(set(codes)), exercise.slug)
            tags.update(codes)
        self.assertEqual(len(tags), 71)
        for code in sorted(tags):
            with self.subTest(code=code):
                self.assertTrue(is_safe_code(code))
                self.assertIn(code, registered)
                self.assertEqual(registered[code].domain, "python")

    def test_catalog_has_no_duplicates_and_describes_each_code(self) -> None:
        codes = [code for code, *_ in CATALOG]
        self.assertEqual(len(codes), len(set(codes)))
        for definition in DEFINITIONS:
            with self.subTest(code=definition.code):
                self.assertTrue(definition.title and definition.description)
                self.assertTrue(definition.category)
        self.assertEqual(
            all_definitions()["range-exclusive-stop"].title, "Treats range stop as inclusive"
        )


class PythonPackDetectionTests(MisconceptionFixtures, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def setUp(self) -> None:
        super().setUp()
        world = World.objects.get(slug=WORLD_SLUG)
        self.pack = Enrollment.objects.create(learner=self.profile, world=world)

    def submit(self, slug: str, answer, **kwargs):
        exercise = Exercise.objects.get(lesson__concept__skill__world__slug=WORLD_SLUG, slug=slug)
        attempt = record_attempt(user=self.user, exercise=exercise, answer=answer, **kwargs)
        self.assertEqual(attempt.enrollment, self.pack)
        return attempt

    def strong(self, attempt) -> set[tuple[str, str]]:
        return set(
            MisconceptionEvidence.objects.filter(attempt=attempt)
            .exclude(source="exercise_tag")
            .values_list("code", "source")
        )

    def starter(self, slug: str) -> str:
        return Exercise.objects.get(slug=slug).content["starter_code"]

    def test_fill_gap_rules(self) -> None:
        self.assertEqual(
            self.strong(self.submit("one-to-five", "5")),
            {
                ("range-exclusive-stop", "python_fill_gap_off_by_one"),
                ("off-by-one", "python_fill_gap_off_by_one"),
            },
        )
        self.assertEqual(
            self.strong(self.submit("below-thirteen", ">")),
            {("comparison-direction", "python_comparison_operator")},
        )
        self.assertEqual(
            self.strong(self.submit("below-thirteen", "<=")),
            {("comparison-boundary", "python_comparison_operator")},
        )
        self.assertEqual(
            self.strong(self.submit("free-shipping-threshold", ">")),
            {("comparison-boundary", "python_comparison_operator")},
        )
        # Correct answers are counter-evidence, never positive.
        correct = self.submit("one-to-five", "6")
        self.assertEqual(
            set(
                MisconceptionEvidence.objects.filter(attempt=correct).values_list("kind", flat=True)
            ),
            {"counter"},
        )

    def test_stdout_code_rules(self) -> None:
        self.use_python_backend(lambda *a: outcome("wrong\n"))
        self.assertEqual(
            self.strong(self.submit("greater-than-ten", self.starter("greater-than-ten"))),
            {("comparison-direction", "python_comparison_operator")},
        )
        self.assertEqual(
            self.strong(self.submit("countdown-step", self.starter("countdown-step"))),
            {("range-step", "python_range_step")},
        )

    def test_function_code_rules(self) -> None:
        self.use_python_backend(
            lambda files, argv, stdin: harness_reply(
                stdin, [{"ok": True, "value": None} for _ in function_calls(stdin)]
            )
        )
        self.assertEqual(
            self.strong(self.submit("voting-age-boundary", self.starter("voting-age-boundary"))),
            {("comparison-boundary", "python_comparison_operator")},
        )
        self.assertEqual(
            self.strong(self.submit("count-up-off-by-one", self.starter("count-up-off-by-one"))),
            {
                ("off-by-one", "python_range_stop"),
                ("range-exclusive-stop", "python_range_stop"),
            },
        )

    def test_runaway_while_loop(self) -> None:
        self.use_python_backend(lambda *a: outcome("1\n" * 100, output_limited=True))
        attempt = self.submit("count-to-five", self.starter("count-to-five"))
        self.assertEqual(attempt.diagnostics, {"reason": "output_limit"})
        self.assertEqual(self.strong(attempt), {("infinite-while", "python_timeout_loop")})

    def test_timeout_elsewhere_is_not_infinite_while(self) -> None:
        self.use_python_backend(lambda *a: outcome(timed_out=True, exit_code=124))
        attempt = self.submit("greater-than-ten", "while True:\n    pass\n")
        self.assertEqual(attempt.diagnostics, {"reason": "timeout"})
        self.assertEqual(self.strong(attempt), set())
        self.assertFalse(MisconceptionState.objects.filter(code="infinite-while").exists())

    def test_indentation_error(self) -> None:
        self.use_python_backend(
            lambda *a: outcome(
                stderr='  File "main.py", line 3\nIndentationError: expected an indented block\n',
                exit_code=1,
            )
        )
        attempt = self.submit("indent-the-branch", self.starter("indent-the-branch"))
        self.assertEqual(attempt.diagnostics["error_type"], "IndentationError")
        self.assertEqual(self.strong(attempt), {("indentation-block", "python_indentation_error")})

    def test_syntax_error_is_not_indentation(self) -> None:
        self.use_python_backend(
            lambda *a: outcome(stderr="SyntaxError: invalid syntax\n", exit_code=1)
        )
        attempt = self.submit("indent-the-branch", "if True print('x')\n")
        self.assertEqual(self.strong(attempt), set())
        self.assertEqual(
            MisconceptionState.objects.get(code="indentation-block").strong_evidence_count, 0
        )

    def test_student_state_lists_pack_misconceptions_safely(self) -> None:
        for _ in range(2):
            self.submit("one-to-five", "5")
        self.submit("below-thirteen", ">")
        self.client.force_login(self.user)
        response = self.client.get(f"/app/worlds/{self.pack.world_id}/learning-state/")
        data = response.json()
        self.assertEqual(data["summary"]["active_misconceptions"], 2)
        self.assertEqual(data["summary"]["watch_misconceptions"], 2)
        listed = {m["code"]: m for c in data["concepts"] for m in c["misconceptions"]}
        self.assertEqual(
            {code: item["status"] for code, item in listed.items()},
            {
                "off-by-one": "active",
                "range-exclusive-stop": "active",
                "comparison-direction": "watch",
                "comparison-boundary": "watch",
            },
        )
        self.assertEqual(listed["off-by-one"]["title"], "Off-by-one error")
        self.assertEqual(set(listed["off-by-one"]), {"code", "title", "status", "confidence"})
        loops = next(
            c
            for c in data["concepts"]
            if c["misconceptions"][:1] and c["misconceptions"][0]["status"] == "active"
        )
        self.assertEqual(
            [m["code"] for m in loops["misconceptions"]], ["off-by-one", "range-exclusive-stop"]
        )
        body = response.content.decode()
        for secret in ("accepted_answers", '"6"', "reference_solution", "evaluation_spec"):
            self.assertNotIn(secret, body)
