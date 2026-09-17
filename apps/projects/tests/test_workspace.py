"""Stage progression, drafts, submissions and completion through the JSON endpoints."""

from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.learner_intelligence.models import ConceptState
from apps.next_action.engine import next_action_for_enrollment
from apps.projects import selectors
from apps.projects.models import ProjectCompletion, ProjectDraft, ProjectSubmission
from apps.projects.services import complete_if_finished
from apps.projects.tests.helpers import (
    BAD,
    GOOD,
    SECRET_DRIVER,
    SECRET_EXPECTED,
    SECRET_FIXTURE,
    ProjectFixtures,
)
from apps.python_runner.exceptions import RunnerUnavailableError


class WorkspaceFixtures(ProjectFixtures):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)

    def stage_page(self, stage):
        return self.client.get(self.url("stage", stage))


class StageProgressionTests(WorkspaceFixtures, TestCase):
    def test_stages_unlock_in_order(self) -> None:
        first, second, third = self.stages
        self.assertEqual(self.stage_page(first).status_code, 200)
        self.assertRedirects(self.stage_page(second), self.url("detail"))
        response = self.submit(second)
        self.assertEqual((response.status_code, response.json()), (409, {"error": "stage_locked"}))

        response = self.submit(first, BAD)
        self.assertEqual(response.json()["status"], "incorrect")
        self.assertRedirects(self.stage_page(second), self.url("detail"))

        response = self.submit(first)
        body = response.json()
        self.assertEqual((body["status"], body["stage_completed"]), ("correct", True))
        self.assertEqual(body["next_stage_url"], self.url("stage", second))
        self.assertFalse(body["project_completed"])
        self.assertEqual(self.stage_page(second).status_code, 200)
        self.assertRedirects(self.stage_page(third), self.url("detail"))

        # State is server-side and survives a reload.
        view = selectors.project_view(self.enrollment, self.project)
        self.assertEqual([s.state for s in view.stages], ["done", "available", "locked"])
        self.assertEqual(view.current_stage.stage, second)

    def test_detail_page_lists_stages_and_next_step(self) -> None:
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "Build an area calculator.")
        self.assertContains(response, "Start project")
        self.submit(self.stages[0])
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "Continue stage 2")
        self.assertContains(response, "1 of 3 stages · 33%")


class DraftTests(WorkspaceFixtures, TestCase):
    def test_first_visit_uses_the_starter_code(self) -> None:
        self.assertContains(self.stage_page(self.stages[0]), "def area(w, h):\n    ...")

    def test_saved_code_is_restored_and_kept_after_failures(self) -> None:
        response = self.post(self.url("draft"), {"stage": "stage-1", "source": "x = 'draft'\n"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("saved_at", response.json())
        self.assertContains(self.stage_page(self.stages[0]), "x = &#x27;draft&#x27;")

        self.submit(self.stages[0], BAD)
        self.assertEqual(ProjectDraft.objects.get().source_code, BAD)
        self.use_backend(lambda *args: (_ for _ in ()).throw(RunnerUnavailableError("down")))
        with self.assertLogs("apps.projects.services", level="ERROR"):
            response = self.submit(self.stages[0], GOOD + "# unavailable\n")
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertIn("Your code is saved", response.json()["feedback"][0])
        self.assertEqual(ProjectDraft.objects.get().source_code, GOOD + "# unavailable\n")
        self.assertEqual(self.stage_page(self.stages[0]).status_code, 200)

    def test_next_stage_starts_from_the_passing_code(self) -> None:
        self.submit(self.stages[0], GOOD + "# stage one\n")
        ProjectDraft.objects.all().delete()
        response = self.stage_page(self.stages[1])
        self.assertContains(response, "# stage one")
        config = response.context["config"]
        self.assertEqual(config["resetSource"], GOOD + "# stage one\n")
        # Stage 1 resets to the project's starter code, never to a solution.
        first = self.stage_page(self.stages[0]).context["config"]
        self.assertEqual(first["resetSource"], "def area(w, h):\n    ...\n")

    def test_draft_validation(self) -> None:
        url = self.url("draft")
        self.assertEqual(self.post(url, {"stage": "stage-1", "source": 5}).status_code, 400)
        self.assertEqual(self.post(url, {"source": "x"}).json(), {"error": "stage_required"})
        response = self.post(url, {"stage": "stage-1", "source": "x" * 70000})
        self.assertEqual(response.json(), {"error": "source_too_large"})
        response = self.post(url, {"stage": "stage-2", "source": "x"})
        self.assertEqual((response.status_code, response.json()["error"]), (409, "stage_locked"))

    def test_other_learners_never_see_or_change_this_draft(self) -> None:
        self.post(self.url("draft"), {"stage": "stage-1", "source": "mine = 1\n"})
        other_user, other_enrollment = self.enroll_other()
        self.master(enrollment=other_enrollment)
        self.client.force_login(other_user)
        self.assertNotContains(self.stage_page(self.stages[0]), "mine = 1")
        self.post(self.url("draft"), {"stage": "stage-1", "source": "theirs = 2\n"})
        drafts = dict(ProjectDraft.objects.values_list("enrollment_id", "source_code"))
        self.assertEqual(drafts[self.enrollment.pk], "mine = 1\n")
        self.assertEqual(drafts[other_enrollment.pk], "theirs = 2\n")


class SubmissionTests(WorkspaceFixtures, TestCase):
    def test_submissions_store_safe_snapshots(self) -> None:
        self.submit(self.stages[0], BAD, duration_seconds=42)
        body = self.submit(self.stages[0], "def area(:\n").json()
        self.assertEqual(body["attempt_number"], 2)
        self.assertEqual(
            body["diagnostics"], {"reason": "syntax_error", "error_type": "SyntaxError"}
        )
        body = self.submit(self.stages[0], "x = 1\n").json()
        self.assertEqual(body["diagnostics"], {"reason": "missing_function", "missing": "area"})
        self.assertIn("Your program needs a function named area.", body["feedback"])
        body = self.submit(self.stages[0], "").json()
        self.assertEqual(
            (body["status"], body["diagnostics"]), ("invalid", {"reason": "empty_answer"})
        )

        first = ProjectSubmission.objects.get(attempt_number=1)
        self.assertEqual(
            (first.status, first.duration_seconds, first.submitted_source),
            ("incorrect", 42, BAD),
        )
        self.assertEqual(first.diagnostics, {"reason": "output_mismatch"})
        for submission in ProjectSubmission.objects.all():
            stored = str(vars(submission))
            for secret in (SECRET_EXPECTED, SECRET_DRIVER, SECRET_FIXTURE, "@@CHECK"):
                self.assertNotIn(secret, stored)

    def test_the_sandbox_gets_the_private_driver_and_fixtures(self) -> None:
        self.submit(self.stages[0])
        request = self.backend.requests[-1]
        self.assertIn(SECRET_DRIVER, request["files"]["learner.py"])
        self.assertEqual(request["files"]["fixtures/data.csv"], SECRET_FIXTURE)

    def test_learner_output_never_comes_back(self) -> None:
        body = self.submit(self.stages[0], BAD).json()
        self.assertNotIn("noise", str(body))
        self.assertNotIn("wrong", str(body))

    def test_invalid_duration(self) -> None:
        response = self.submit(self.stages[0], duration_seconds=-1)
        self.assertEqual(response.json(), {"error": "invalid_duration"})
        self.assertFalse(ProjectSubmission.objects.exists())

    def test_runner_disabled_is_unsupported(self) -> None:
        from apps.projects.evaluation.python import PythonProjectEvaluator
        from apps.python_runner.tests.fakes import DISABLED

        disabled = PythonProjectEvaluator(config_provider=lambda: DISABLED)
        with mock.patch("apps.projects.services.evaluator_for", return_value=disabled):
            body = self.submit(self.stages[0]).json()
        self.assertEqual(body["status"], "unsupported")
        self.assertFalse(body["stage_completed"])


class CompletionTests(WorkspaceFixtures, TestCase):
    def test_completion_happens_once(self) -> None:
        self.submit(self.stages[0])
        self.submit(self.stages[1])
        self.assertFalse(ProjectCompletion.objects.exists())
        body = self.submit(self.stages[2]).json()
        self.assertTrue(body["project_completed"])
        self.assertEqual(body["next_stage_url"], "")
        completion = ProjectCompletion.objects.get()
        self.assertEqual(completion.final_submission.stage, self.stages[2])

        body = self.submit(self.stages[2]).json()
        self.assertTrue(body["project_completed"])
        self.assertEqual(ProjectCompletion.objects.count(), 1)
        self.assertEqual(
            selectors.project_view(self.enrollment, self.project).state, selectors.COMPLETED
        )
        page = self.client.get(self.url("detail"))
        self.assertContains(page, "Completed ")

    def test_a_lost_completion_race_is_harmless(self) -> None:
        self.complete_all()
        submission = ProjectSubmission.objects.last()
        with mock.patch.object(
            ProjectCompletion.objects, "get_or_create", side_effect=IntegrityError("dup")
        ):
            self.assertTrue(complete_if_finished(self.enrollment, self.project, submission))
        self.assertEqual(ProjectCompletion.objects.count(), 1)

    def test_projects_do_not_change_learning_state(self) -> None:
        now = timezone.now()
        before_states = list(ConceptState.objects.values_list("mastery_score", "mastery_band"))
        before_decision = next_action_for_enrollment(self.enrollment, now=now)
        self.complete_all()
        self.assertEqual(
            list(ConceptState.objects.values_list("mastery_score", "mastery_band")),
            before_states,
        )
        self.assertEqual(next_action_for_enrollment(self.enrollment, now=now), before_decision)
