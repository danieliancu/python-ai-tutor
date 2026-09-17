"""End-to-end player flows through the existing JSON endpoints (as the page's JS calls them)."""

import json
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.tests.helpers import ENABLED as TUTOR_ENABLED
from apps.attempts.models import ExerciseAttempt
from apps.attempts.tests.helpers import SECRET_GAP, SECRET_OPTION, SECRET_OUTPUT
from apps.course_player.tests.helpers import PlayerFixtures, page_config
from apps.curriculum.models import SkillPrerequisite
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.models import ConceptState
from apps.python_runner.tests.fakes import outcome

MCQ = {"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]}


class AttemptFlowTests(PlayerFixtures, TestCase):
    def progress(self, exercise=None):
        url = reverse("course_player:progress", args=[self.python_world.pk])
        return self.client.get(url + (f"?exercise={exercise.pk}" if exercise else ""))

    def test_multiple_choice_attempt_refreshes_progress_and_next_up(self) -> None:
        config = page_config(self.open())
        self.assertEqual(config["exercise"]["id"], self.mcq.pk)
        before = self.client.get(config["urls"]["nextAction"]).json()
        self.assertEqual(before["exercise"]["id"], self.mcq.pk)
        self.assertContains(self.progress(), '<span class="ring__label">0%</span>')

        response = self.attempt(self.mcq, {"answer": SECRET_OPTION, "duration_seconds": 42})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "correct")
        attempt = ExerciseAttempt.objects.get()
        self.assertEqual((attempt.duration_seconds, attempt.submitted_answer), (42, SECRET_OPTION))

        # Mastery comes from Learner Intelligence (one correct recognise answer = 60).
        state = ConceptState.objects.get(enrollment=self.enrollment)
        self.assertEqual(state.mastery_score, Decimal("60.00"))
        fragment = self.progress(self.mcq)
        self.assertContains(fragment, '<span class="ring__label">60%</span>')
        self.assertContains(fragment, 'stroke-dasharray="60 100"')
        self.assertContains(fragment, 'aria-current="step"')
        learning = self.client.get(
            reverse("learner_intelligence:learning_state", args=[self.python_world.pk])
        ).json()
        self.assertEqual(learning["summary"]["mastery"], 60.0)

        after = self.client.get(config["urls"]["nextAction"]).json()
        self.assertEqual(after["exercise"]["id"], self.gap.pk)
        self.assertEqual(
            self.open().context["lesson"]["next_up"]["href"],
            f"{config['urls']['player']}?exercise={self.gap.pk}",
        )

    def test_fill_gap_numeric_and_text_answers(self) -> None:
        self.assertEqual(self.attempt(self.gap, {"answer": SECRET_GAP}).json()["status"], "correct")
        maths = self.client.post(
            reverse("attempts:exercise_attempts", args=[self.numeric.pk]),
            data=json.dumps({"answer": 4321.25, "duration_seconds": 5}),
            content_type="application/json",
        )
        self.assertEqual(maths.json()["status"], "correct")
        as_text = self.attempt(self.numeric, {"answer": "4321.25"})
        self.assertEqual(as_text.json()["status"], "correct")
        invalid = self.attempt(self.numeric, {"answer": "twelve"})
        self.assertEqual(invalid.json()["status"], "invalid")
        text = self.attempt(self.text, {"answer": "Loops repeat work."})
        self.assertEqual(text.json()["status"], "review_required")
        self.assertContains(self.open(self.text), "needs a review")

    def test_code_attempt_with_fake_runner(self) -> None:
        self.use_python_backend(lambda *a: outcome(SECRET_OUTPUT + "\n"))
        response = self.attempt(self.code, {"answer": "print('x')\n", "duration_seconds": 90})
        body = response.json()
        self.assertEqual(body["status"], "correct")
        self.assertNotIn(SECRET_OUTPUT, json.dumps(body))
        self.assertContains(self.open(self.code), "✓ Correct.")

    def test_code_without_runner_is_unsupported_not_wrong(self) -> None:
        response = self.attempt(self.code, {"answer": "print(1)"})
        self.assertEqual(response.json()["status"], "unsupported")
        page = self.open(self.code)
        self.assertContains(page, "can&#x27;t be checked automatically yet")

    def test_runtime_errors_show_the_error_type_only(self) -> None:
        self.use_python_backend(
            lambda *a: outcome(stderr="NameError: name 'SECRET' is not defined\n", exit_code=1)
        )
        self.attempt(self.code, {"answer": "print(x)"})
        page = self.open(self.code)
        self.assertContains(page, "Error: NameError")
        self.assertContains(page, 'class="console__tab is-active" data-tab-errors')
        self.assertNotContains(page, "is not defined")

    def test_csrf_is_required(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        page = client.get(reverse("course_player:world", args=[self.python_world.pk]))
        token = page.context["csrf_token"]
        blocked = client.post(
            reverse("attempts:exercise_attempts", args=[self.mcq.pk]),
            data=json.dumps({"answer": "opt-a"}),
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 403)
        allowed = client.post(
            reverse("attempts:exercise_attempts", args=[self.mcq.pk]),
            data=json.dumps({"answer": "opt-a"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=str(token),
        )
        self.assertEqual(allowed.status_code, 201)

    def test_pending_tutor_turn_blocks_the_attempt(self) -> None:
        TutorTurn.objects.create(
            enrollment=self.enrollment,
            exercise=self.gap,
            requested_intent="hint",
            response_kind="hint",
            status="pending",
            prompt_version=1,
        )
        response = self.attempt(self.gap, {"answer": "x"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "tutor_turn_in_progress")
        self.assertFalse(ExerciseAttempt.objects.exists())


class SkillMapTests(PlayerFixtures, TestCase):
    def state(self, concept, mastery, band):
        return ConceptState.objects.create(
            enrollment=self.enrollment,
            concept=concept,
            mastery_score=Decimal(mastery),
            mastery_band=band,
            trend="stable",
            evidence_count=3,
            correct_count=3,
            review_due_at=timezone.now() + timedelta(days=30),
        )

    def test_states_come_from_learner_state(self) -> None:
        first = self.concept.skill
        mastered_skill = make_skill(self.python_world, "Done skill")
        done = make_concept(mastered_skill)
        make_exercise(
            make_lesson(done),
            response_type="multiple_choice",
            content=MCQ,
            evaluation_spec={"correct_option": "a"},
        )
        practising_skill = make_skill(self.python_world, "Practising skill")
        practising = make_concept(practising_skill)
        make_exercise(
            make_lesson(practising),
            response_type="multiple_choice",
            content=MCQ,
            evaluation_spec={"correct_option": "a"},
        )
        locked_skill = make_skill(self.python_world, "Locked skill")
        locked = make_concept(locked_skill)
        make_exercise(
            make_lesson(locked),
            response_type="multiple_choice",
            content=MCQ,
            evaluation_spec={"correct_option": "a"},
        )
        SkillPrerequisite.objects.create(skill=locked_skill, prerequisite=practising_skill)
        ready_skill = make_skill(self.python_world, "Ready skill")
        ready = make_concept(ready_skill)
        make_exercise(
            make_lesson(ready),
            response_type="multiple_choice",
            content=MCQ,
            evaluation_spec={"correct_option": "a"},
        )
        self.state(done, "95", "mastered")
        self.state(practising, "70", "practising")
        # The practising skill has a second, unstarted concept, so the locked skill stays locked.
        make_concept(practising_skill)

        states = {
            s["name"]: (s["state"], s["current"]) for s in self.open(self.mcq).context["skills"]
        }
        self.assertEqual(states[first.title], ("learning", True))
        self.assertEqual(states["Done skill"], ("mastered", False))
        self.assertEqual(states["Practising skill"], ("practising", False))
        self.assertEqual(states["Locked skill"], ("locked", False))
        self.assertEqual(states["Ready skill"], ("available", False))
        page = self.open(self.mcq)
        self.assertContains(page, 'data-state="mastered"')
        self.assertContains(page, "READY")
        self.assertNotContains(page, "DEMO")

    def test_mobile_window_marks_extra_skills(self) -> None:
        for index in range(8):
            make_skill(self.python_world, f"Extra {index}")
        skills = self.open(self.mcq).context["skills"]
        self.assertEqual(sum(not s["extra"] for s in skills), 5)
        self.assertFalse(next(s for s in skills if s["current"])["extra"])


class TutorFlowTests(PlayerFixtures, TestCase):
    def test_history_is_rendered_safely(self) -> None:
        provider = self.enable_tutor(FakeTutorProvider(reply="<script>alert(1)</script> Look at"))
        response = self.tutor({"message": "<b>why?</b>", "exercise_id": self.mcq.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(provider.requests), 1)
        page = self.open(self.mcq)
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt; Look at")
        self.assertContains(page, "&lt;b&gt;why?&lt;/b&gt;")
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "bubble bubble--learner")
        self.assertContains(page, "Beta")
        self.assertTrue(page_config(page)["tutorAvailable"])

    def test_failed_turns_are_not_shown(self) -> None:
        self.enable_tutor()
        TutorTurn.objects.create(
            enrollment=self.enrollment,
            requested_intent="ask",
            user_message="hidden failure",
            status="failed",
            error_code="provider_timeout",
            prompt_version=1,
        )
        self.assertNotContains(self.open(), "hidden failure")

    def test_commands_follow_the_server_ladder(self) -> None:
        self.enable_tutor()
        kinds = [
            self.tutor({"intent": "solution", "message": "", "exercise_id": self.gap.pk}).json()[
                "response_kind"
            ]
            for _ in range(4)
        ]
        self.assertEqual(kinds, ["hint", "strong_hint", "explanation", "solution"])
        hint = self.tutor({"intent": "hint", "message": "", "exercise_id": self.mcq.pk}).json()
        self.assertEqual(hint["response_kind"], "hint")
        nxt = self.tutor({"intent": "next_step", "message": ""}).json()
        self.assertEqual(nxt["response_kind"], "next_step")
        explain = self.tutor({"intent": "explain", "message": "", "exercise_id": self.mcq.pk})
        self.assertEqual(explain.json()["response_kind"], "strong_hint")

    def test_tutor_help_is_attached_to_the_next_attempt(self) -> None:
        self.enable_tutor()
        for _ in range(4):
            self.tutor({"intent": "solution", "message": "", "exercise_id": self.gap.pk})
        response = self.attempt(self.gap, {"answer": SECRET_GAP, "duration_seconds": 30})
        body = response.json()
        self.assertEqual(
            (body["hint_level"], body["used_explanation"], body["used_solution"]), (2, True, True)
        )

    def test_in_progress_turn_returns_409(self) -> None:
        self.enable_tutor()
        TutorTurn.objects.create(
            enrollment=self.enrollment,
            exercise=self.gap,
            requested_intent="hint",
            response_kind="hint",
            status="pending",
            prompt_version=1,
        )
        response = self.tutor({"intent": "hint", "message": "", "exercise_id": self.gap.pk})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "tutor_turn_in_progress")

    def test_unavailable_tutor_keeps_the_player_usable(self) -> None:
        with override_settings(AI_TUTOR={**TUTOR_ENABLED, "OPENAI_API_KEY": ""}):
            page = self.open(self.mcq)
            self.assertContains(page, "AI Tutor is currently unavailable.")
            self.assertContains(page, "Offline")
            self.assertFalse(page_config(page)["tutorAvailable"])
            response = self.tutor({"message": "hi", "exercise_id": self.mcq.pk})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["error"], "tutor_unavailable")
            attempt = self.attempt(self.mcq, {"answer": SECRET_OPTION})
            self.assertEqual(attempt.status_code, 201)

    def test_tutor_csrf_is_required(self) -> None:
        self.enable_tutor()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.tutor({"message": "hi"}, client=client)
        self.assertEqual(response.status_code, 403)
