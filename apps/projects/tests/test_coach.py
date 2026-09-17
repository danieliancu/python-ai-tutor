import json

from django.test import Client, TestCase

from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.providers.base import TutorTimeout
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.selectors import recent_completed_turns
from apps.ai_tutor.tests.helpers import FORBIDDEN_KEYS, keys
from apps.curriculum.tests.helpers import make_world
from apps.learners.models import Enrollment
from apps.projects.coach import grant_project_kind, leaks_project_solution
from apps.projects.tests.helpers import (
    BAD,
    SECRET_DRIVER,
    SECRET_EXPECTED,
    SECRET_FIXTURE,
    ProjectFixtures,
)

LONG_CODE = "```python\n" + "\n".join(f"line_{n} = {n}" for n in range(20)) + "\n```"


class CoachTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)
        self.provider = self.enable_tutor()

    def ask(self, intent="ask", message="Why does my area look wrong?", stage=None, **extra):
        body = {"intent": intent, "message": message, **extra}
        return self.post(self.url("coach", stage or self.stages[0]), body)

    def request(self):
        return self.provider.requests[-1]

    def test_context_is_public_project_text_and_learner_code(self) -> None:
        self.submit(self.stages[0], BAD)
        response = self.ask(source="def area(w, h):\n    return w - h  # MY CODE\n")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["response_kind"], "feedback")
        request = self.request()
        context = request.server_context
        self.assertEqual(context["project"]["title"], "Area Tool")
        self.assertEqual(context["project"]["brief"], "Build an area calculator.")
        self.assertEqual(context["stage"]["objective"], "Objective 1")
        self.assertEqual(context["stage"]["requirements"], ["Requirement 1"])
        self.assertEqual((context["stage"]["number"], context["stage"]["total"]), (1, 3))
        self.assertEqual(
            context["evaluation"]["latest_submission"]["diagnostics"],
            {"reason": "output_mismatch"},
        )
        self.assertEqual(
            {row["concept"] for row in context["required_concepts"]},
            {self.concept_a.title, "Loops"},
        )
        self.assertIn("# MY CODE", request.learner_submission.text)
        self.assertEqual(request.user_message, "Why does my area look wrong?")
        self.assertIn("Never write the finished program", request.instructions)

    def test_hidden_checks_never_reach_the_model(self) -> None:
        self.submit(self.stages[0], BAD)
        self.ask("hint", "")
        request = self.request()
        self.assertFalse(keys(request.server_context) & FORBIDDEN_KEYS)
        self.assertFalse(
            keys(request.server_context) & {"driver", "fixtures", "requires", "function_name"}
        )
        everything = json.dumps(request.server_context) + request.instructions
        everything += request.learner_submission.text if request.learner_submission else ""
        for secret in (SECRET_DRIVER, SECRET_FIXTURE, SECRET_EXPECTED, "SECRET-FIXTURE-ROW"):
            self.assertNotIn(secret, everything)

    def test_uses_the_draft_when_no_code_is_sent(self) -> None:
        self.post(self.url("draft"), {"stage": "stage-1", "source": "draft_code = True\n"})
        self.ask()
        self.assertIn("draft_code = True", self.request().learner_submission.text)

    def test_solution_requests_never_get_a_solution(self) -> None:
        kinds = [self.ask("solution", "Give me the full solution").json()["response_kind"]]
        kinds.append(self.ask("hint", "").json()["response_kind"])
        self.assertEqual(kinds, ["strong_hint", "strong_hint"])
        self.assertFalse(self.request().solution_allowed)
        self.assertIn("must NOT be revealed", self.request().instructions)
        self.assertEqual(
            [
                grant_project_kind(intent, hints_used=0, has_submission=False)
                for intent in ("ask", "hint", "explain", "solution", "next_step")
            ],
            ["guidance", "hint", "explanation", "strong_hint", "next_step"],
        )

    def test_full_program_replies_are_rejected(self) -> None:
        self.provider.reply = "Here you go:\n" + LONG_CODE
        response = self.ask()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "tutor_unavailable")
        turn = TutorTurn.objects.get()
        self.assertEqual((turn.status, turn.error_code), ("failed", "provider_invalid_response"))
        self.assertTrue(
            leaks_project_solution("```\ndef area(w, h):\n    return w * h\n```", {"area"})
        )
        self.assertFalse(leaks_project_solution("```\nprint(3 * 4)\n```", {"area"}))
        self.assertFalse(leaks_project_solution("Use `w * h` in area.", {"area"}))

    def test_history_persists_and_stays_separate_from_exercises(self) -> None:
        self.ask(message="First question")
        page = self.client.get(self.url("stage", self.stages[0]))
        self.assertContains(page, "First question")
        self.assertContains(page, "Let&#x27;s look at this together. (guidance)")
        turn = TutorTurn.objects.get()
        self.assertEqual(
            (turn.project, turn.project_stage, turn.exercise), (self.project, self.stages[0], None)
        )
        self.assertEqual(recent_completed_turns(self.enrollment, 10), [])
        self.ask(message="Second question")
        self.assertEqual([item.user_message for item in self.request().history], ["First question"])

    def test_one_reply_at_a_time(self) -> None:
        TutorTurn.objects.create(
            enrollment=self.enrollment,
            project=self.project,
            project_stage=self.stages[0],
            requested_intent="ask",
            prompt_version=1,
        )
        response = self.ask()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "tutor_turn_in_progress")

    def test_provider_errors_and_disabled_tutor(self) -> None:
        self.provider.error = TutorTimeout()
        self.assertEqual(self.ask().status_code, 503)
        self.provider.error = None
        with self.settings(AI_TUTOR={"ENABLED": False}):
            self.assertEqual(self.ask().json()["error"], "tutor_unavailable")
            page = self.client.get(self.url("stage", self.stages[0]))
            self.assertContains(page, "AI Tutor is currently unavailable.")
            self.assertEqual(self.submit(self.stages[0]).status_code, 201)

    def test_rate_limit_and_validation(self) -> None:
        self.assertEqual(self.ask("ask", "").json()["error"], "message_required")
        self.assertEqual(self.ask("dance").json()["error"], "invalid_intent")
        self.assertEqual(self.ask(source=5).json()["error"], "invalid_source")
        with self.settings(AI_TUTOR={**self.tutor_settings(), "RATE_LIMIT_PER_MINUTE": 1}):
            self.assertEqual(self.ask().status_code, 201)
            self.assertEqual(self.ask().status_code, 429)

    def tutor_settings(self):
        from apps.ai_tutor.tests.helpers import ENABLED

        return dict(ENABLED)

    def test_locked_stage_and_other_learners(self) -> None:
        response = self.ask(stage=self.stages[1])
        self.assertEqual((response.status_code, response.json()["error"]), (409, "stage_locked"))
        other_user, _ = self.enroll_other()
        other = Client()
        other.force_login(other_user)
        self.post(self.url("coach", self.stages[0]), {"intent": "ask", "message": "hi"}, other)
        self.ask(message="mine")
        mine = [turn.user_message for turn in TutorTurn.objects.filter(enrollment=self.enrollment)]
        self.assertEqual(mine, ["mine"])
        stranger_world = make_world("Other")
        Enrollment.objects.create(learner=self.profile, world=stranger_world)
        response = self.post(
            self.url("coach", self.stages[0], world=stranger_world),
            {"intent": "ask", "message": "hi"},
        )
        self.assertEqual(response.status_code, 404)

    def test_replies_are_escaped(self) -> None:
        self.provider = self.enable_tutor(FakeTutorProvider(reply="<script>alert(1)</script>"))
        self.ask(message="<b>bold</b>")
        page = self.client.get(self.url("stage", self.stages[0]))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertNotContains(page, "<b>bold</b>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")
