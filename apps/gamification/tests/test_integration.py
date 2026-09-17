import json
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.attempts.models import ExerciseAttempt
from apps.attempts.services import POST_ATTEMPT_STEPS
from apps.attempts.tests.helpers import SECRET_OPTION
from apps.gamification.models import (
    Achievement,
    AchievementAward,
    GamificationProfile,
    XPEvent,
)
from apps.gamification.services import sync_enrollment_exercise, sync_learner
from apps.gamification.tests.helpers import GamificationFixtures
from apps.learner_intelligence.models import ConceptState


class PipelineTests(GamificationFixtures, TestCase):
    def test_runs_after_learning_state_and_before_tutor_bookkeeping(self) -> None:
        labels = [step[0] for step in POST_ATTEMPT_STEPS]
        self.assertEqual(
            labels, ["Learner intelligence", "Misconception", "Gamification", "Tutor assistance"]
        )
        self.assertIn("rebuild_gamification", POST_ATTEMPT_STEPS[2][3])

    def test_a_failure_never_loses_the_attempt(self) -> None:
        with (
            mock.patch(
                "apps.gamification.services.refresh_for_attempt", side_effect=RuntimeError("boom")
            ),
            self.assertLogs("apps.attempts.services", level="ERROR") as logs,
        ):
            attempt = self.correct_mcq()
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(ConceptState.objects.filter(enrollment=self.enrollment).exists())
        self.assertFalse(XPEvent.objects.exists())
        self.assertIn("rebuild_gamification", "\n".join(logs.output))
        # The rebuild command repairs it.
        call_command("rebuild_gamification", stdout=mock.Mock())
        self.assertEqual(GamificationProfile.objects.get(learner=self.profile).total_xp, 30)

    def test_a_lost_insert_race_is_treated_as_already_awarded(self) -> None:
        self.correct_mcq()
        XPEvent.objects.all().delete()
        with mock.patch.object(
            XPEvent.objects, "get_or_create", side_effect=IntegrityError("duplicate")
        ):
            self.assertEqual(sync_enrollment_exercise(self.enrollment, self.mcq), 0)
        with mock.patch.object(
            AchievementAward.objects, "get_or_create", side_effect=IntegrityError("duplicate")
        ):
            AchievementAward.objects.all().delete()
            self.assertEqual(sync_learner(self.profile), [])

    def test_gamification_does_not_change_learning_state(self) -> None:
        self.correct_mcq()
        state = ConceptState.objects.get(enrollment=self.enrollment)
        before = (state.mastery_score, state.mastery_band)
        XPEvent.objects.update(xp=1000)
        sync_learner(self.profile)
        state.refresh_from_db()
        self.assertEqual((state.mastery_score, state.mastery_band), before)


class SummaryEndpointTests(GamificationFixtures, TestCase):
    url = reverse("gamification:summary")

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def submit(self, answer, client=None):
        response = (client or self.client).post(
            reverse("attempts:exercise_attempts", args=[self.mcq.pk]),
            data=json.dumps({"answer": answer}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_stats_without_an_attempt(self) -> None:
        body = self.client.get(self.url).json()
        self.assertEqual(
            body,
            {"xp": 0, "xp_display": "0", "level": 1, "level_percent": 0, "streak_days": 0},
        )

    def test_rewards_for_the_learners_own_attempt(self) -> None:
        wrong = self.submit("opt-a")
        body = self.client.get(self.url, {"attempt": wrong}).json()
        self.assertEqual(body["rewards"], {"xp": 0, "achievements": []})
        self.assertEqual(body["streak_days"], 1)

        right = self.submit(SECRET_OPTION)
        body = self.client.get(self.url, {"attempt": right}).json()
        self.assertEqual(body["xp"], 25)
        self.assertEqual(body["level_percent"], 25)
        self.assertEqual(body["rewards"]["xp"], 25)
        self.assertEqual(
            [a["title"] for a in body["rewards"]["achievements"]],
            ["First Step", "Independent Thinker"],
        )

        again = self.submit(SECRET_OPTION)
        body = self.client.get(self.url, {"attempt": again}).json()
        self.assertEqual((body["xp"], body["rewards"]), (25, {"xp": 0, "achievements": []}))

    def test_other_learners_attempts_are_hidden(self) -> None:
        attempt = self.submit(SECRET_OPTION)
        other = Client()
        other.force_login(make_user("someone-else"))
        self.assertEqual(other.get(self.url, {"attempt": attempt}).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"attempt": "abc"}).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"attempt": "999999"}).status_code, 404)

    def test_requires_sign_in_and_get(self) -> None:
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_no_client_supplied_xp_is_trusted(self) -> None:
        response = self.client.post(
            reverse("attempts:exercise_attempts", args=[self.mcq.pk]),
            data=json.dumps({"answer": "opt-a", "xp": 500, "is_correct": True}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, (201, 400))
        self.assertFalse(XPEvent.objects.exists())
        self.assertEqual(Achievement.objects.count(), 7)
