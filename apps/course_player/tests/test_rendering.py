import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.tests.helpers import make_user
from apps.attempts.tests.helpers import (
    SECRET_GAP,
    SECRET_NUMBER,
    SECRET_OUTPUT,
    SECRET_SOLUTION,
)
from apps.course_player.services import fill_gap_lines
from apps.course_player.tests.helpers import PlayerFixtures, page_config, player_url
from apps.curriculum.models import World
from apps.exercises.models import Exercise, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learners.models import Enrollment, LearnerProfile

FORBIDDEN = (
    "evaluation_spec",
    "reference_solution",
    "correct_option",
    "accepted_answers",
    "expected_stdout",
    "reference_answers",
    '"tests"',
    SECRET_GAP,
    SECRET_OUTPUT,
    SECRET_SOLUTION,
    str(SECRET_NUMBER),
)


class ResponseTypeRenderingTests(PlayerFixtures, TestCase):
    def assertSafe(self, response) -> None:
        html = response.content.decode()
        for secret in FORBIDDEN:
            self.assertNotIn(secret, html)

    def test_code_editor_holds_the_starter_code(self) -> None:
        response = self.open(self.code)
        self.assertContains(response, '<textarea id="code-answer" class="code-field__input"')
        self.assertContains(response, "# write here")
        self.assertContains(response, "Run Code")
        self.assertContains(response, "data-reset")
        self.assertEqual(page_config(response)["exercise"]["starterCode"], "# write here\n")
        self.assertEqual(page_config(response)["exercise"]["responseType"], "code")
        self.assertSafe(response)

    def test_multiple_choice_options(self) -> None:
        response = self.open(self.mcq)
        self.assertContains(response, 'type="radio" name="answer" value="opt-a"')
        self.assertContains(response, "value &gt;= 10")
        self.assertContains(response, "Check answer")
        self.assertNotContains(response, "data-reset")
        self.assertSafe(response)

    def test_fill_gap_input_sits_in_the_template(self) -> None:
        response = self.open(self.gap)
        self.assertContains(
            response,
            '<span class="ln">print(<label for="gap-answer" class="visually-hidden">Missing piece'
            '</label><input id="gap-answer" class="gap-input"',
        )
        self.assertSafe(response)
        self.assertEqual(
            fill_gap_lines("for n in range(1, __):\n    print(n)"),
            [
                [{"text": "for n in range(1, "}, {"gap": True}, {"text": "):"}],
                [{"text": "    print(n)"}],
            ],
        )
        self.assertEqual(
            fill_gap_lines("a\n__"), [[{"text": "a"}], [{"text": ""}, {"gap": True}, {"text": ""}]]
        )
        self.assertEqual(fill_gap_lines(""), [[{"gap": True}]])

    def test_numeric_input_and_unit(self) -> None:
        response = self.open(self.numeric, world=self.maths_world)
        self.assertContains(response, 'id="line-answer" class="answer-input"')
        self.assertContains(response, 'inputmode="decimal"')
        self.assertContains(response, '<span class="answer-field__unit">cm</span>')
        self.assertEqual(page_config(response)["exercise"]["responseType"], "numeric")
        self.assertSafe(response)

    def test_text_and_translation(self) -> None:
        response = self.open(self.text)
        self.assertContains(response, 'id="text-answer" class="answer-text"')
        self.assertContains(response, "Written Answer")
        translation = self.open(self.translation, world=self.english_world)
        self.assertContains(translation, "Salut")
        self.assertContains(translation, 'class="answer-text"')
        self.assertSafe(translation)

    def test_unsupported_types_fall_back_safely(self) -> None:
        speaking = make_exercise(self.mcq.lesson, response_type=ResponseType.SPEAKING, content={})
        response = self.open(speaking)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "can't be answered in the browser yet")
        self.assertContains(response, 'data-run disabled aria-disabled="true"')

    def test_learner_html_is_escaped(self) -> None:
        self.record(self.text, "<script>alert(1)</script>")
        response = self.open(self.text)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.code.content = {
            "language": "python",
            "starter_code": "</textarea><script>x()</script>",
        }
        self.code.save()
        response = self.open(self.code)
        self.assertNotContains(response, "</textarea><script>")
        self.assertContains(response, "&lt;/textarea&gt;&lt;script&gt;")

    def test_latest_attempt_feedback_is_shown(self) -> None:
        self.record(self.gap, "wrong")
        response = self.open(self.gap)
        self.assertContains(response, "✗ Not quite yet.")
        self.assertContains(response, "Reason: incorrect value")
        self.assertNotContains(response, "wrong</samp>")


class PythonPackRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def test_every_pack_exercise_renders_safely(self) -> None:
        user = make_user("learner")
        world = World.objects.get(slug="python-foundations")
        Enrollment.objects.create(learner=LearnerProfile.objects.create(user=user), world=world)
        self.client.force_login(user)
        exercises = Exercise.objects.filter(lesson__concept__skill__world=world).select_related(
            "lesson"
        )
        self.assertEqual(exercises.count(), 147)
        types = set(exercises.values_list("response_type", flat=True))
        self.assertEqual(types, {"code", "multiple_choice", "fill_gap", "text"})
        for exercise in exercises:
            with self.subTest(exercise=exercise.slug):
                response = self.client.get(player_url(world, exercise))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("data-exercise-form", html)
                self.assertNotIn("disabled aria-disabled", html.split("data-run", 1)[1][:40])
                spec = exercise.evaluation_spec
                secrets = [spec.get("reference_solution"), spec.get("correct_option")]
                secrets += [json.dumps(a) for a in spec.get("accepted_answers", [])]
                secrets += [
                    t.get("expected_stdout") for t in spec.get("tests", []) if isinstance(t, dict)
                ]
                config = json.dumps(page_config(response))
                for secret in filter(None, secrets):
                    if len(secret) > 4:
                        self.assertNotIn(secret, config)
                self.assertNotIn("evaluation_spec", html)
                self.assertNotIn("reference_solution", html)
        fresh = self.client.get(player_url(world))
        self.assertEqual(
            fresh.context["player"]["exercise"]["id"],
            Exercise.objects.get(slug="top-to-bottom-order").pk,
        )
