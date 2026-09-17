from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.attempts.tests.helpers import SECRET_OPTION
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.gamification import achievements as codes
from apps.gamification.models import AchievementAward, GamificationProfile, XPEvent, XPEventType
from apps.gamification.services import rebuild_gamification, sync_learner
from apps.projects.models import Project, ProjectStage, ProjectSubmission
from apps.projects.tests.helpers import BAD, ProjectFixtures, stdout_spec

D = date(2026, 6, 1)


def at_noon(day):
    return timezone.make_aware(datetime.combine(day, time(12)))


class ProjectRewardTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)

    def project_events(self):
        return list(
            XPEvent.objects.filter(event_type=XPEventType.PROJECT_COMPLETED).values_list(
                "source_key", "xp", "world_id", "enrollment_id"
            )
        )

    def test_completion_awards_project_xp_once(self) -> None:
        self.submit(self.stages[0])
        self.submit(self.stages[1])
        self.assertEqual(self.project_events(), [])
        body = self.submit(self.stages[2]).json()
        self.assertEqual(body["rewards"]["xp"], 150)
        self.assertEqual([a["title"] for a in body["rewards"]["achievements"]], ["Project Builder"])
        self.assertEqual(body["stats"]["xp_display"], "150")
        self.assertEqual(body["stats"]["level"], 2)
        self.assertEqual(
            self.project_events(),
            [(f"project:{self.project.pk}:completed", 150, self.world.pk, self.enrollment.pk)],
        )

        again = self.submit(self.stages[2]).json()
        self.assertEqual(again["rewards"], {"xp": 0, "achievements": []})
        self.assertEqual(len(self.project_events()), 1)
        self.assertEqual(GamificationProfile.objects.get().total_xp, 150)

    def test_stages_alone_earn_no_xp(self) -> None:
        body = self.submit(self.stages[0]).json()
        self.assertEqual(body["rewards"]["xp"], 0)
        self.assertFalse(XPEvent.objects.exists())

    def test_project_builder_is_awarded_once_across_projects(self) -> None:
        self.complete_all()
        second = Project.objects.create(
            world=self.world,
            title="Second",
            slug="second",
            summary="s",
            brief="b",
            order=2,
            estimated_minutes=5,
            xp_reward=100,
            is_published=True,
        )
        stage = ProjectStage.objects.create(
            project=second,
            title="Only",
            slug="only",
            objective="o",
            instructions="i",
            order=1,
            estimated_minutes=5,
            evaluation_spec=stdout_spec(),
            is_published=True,
        )
        body = self.post(
            self.url("submit", stage, project=second), {"source": "def area(w, h): return w * h\n"}
        ).json()
        self.assertTrue(body["project_completed"])
        self.assertEqual(body["rewards"], {"xp": 100, "achievements": []})
        self.assertEqual(
            AchievementAward.objects.filter(achievement__code=codes.PROJECT_BUILDER).count(), 1
        )
        self.assertEqual(GamificationProfile.objects.get().total_xp, 250)

    def test_rebuild_recreates_project_rewards(self) -> None:
        self.complete_all()
        XPEvent.objects.all().delete()
        AchievementAward.objects.all().delete()
        GamificationProfile.objects.all().delete()
        rebuild_gamification()
        rebuild_gamification()
        self.assertEqual(len(self.project_events()), 1)
        self.assertEqual(GamificationProfile.objects.get().total_xp, 150)
        self.assertTrue(
            AchievementAward.objects.filter(achievement__code=codes.PROJECT_BUILDER).exists()
        )

    def test_a_gamification_failure_keeps_the_submission(self) -> None:
        from unittest import mock

        with (
            mock.patch(
                "apps.gamification.services.refresh_for_project_submission",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("apps.projects.services", level="ERROR") as logs,
        ):
            response = self.submit(self.stages[0])
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ProjectSubmission.objects.exists())
        self.assertIn("rebuild_gamification", "\n".join(logs.output))


class ProjectStreakTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)

    def move(self, day):
        latest = ProjectSubmission.objects.order_by("-id").first()
        ProjectSubmission.objects.filter(pk=latest.pk).update(submitted_at=at_noon(day))

    def streak(self):
        sync_learner(self.profile)
        profile = GamificationProfile.objects.get()
        return profile.current_streak, profile.longest_streak

    def test_judged_project_work_counts_as_a_learning_day(self) -> None:
        self.submit(self.stages[0], BAD)
        self.move(D)
        self.submit(self.stages[0])
        self.move(D + timedelta(days=1))
        self.assertEqual(self.streak(), (2, 2))

    def test_unjudged_project_work_does_not_count(self) -> None:
        self.submit(self.stages[0], "")  # invalid
        self.move(D)
        self.assertEqual(self.streak(), (0, 0))

    def test_exercise_and_project_on_the_same_day_count_once(self) -> None:
        mcq = make_exercise(
            self.concept_a.lessons.first(),
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "A"}, {"id": SECRET_OPTION, "text": "B"}]},
            evaluation_spec={"correct_option": SECRET_OPTION},
        )
        from apps.attempts.services import record_attempt

        attempt = record_attempt(user=self.user, exercise=mcq, answer=SECRET_OPTION)
        type(attempt).objects.filter(pk=attempt.pk).update(submitted_at=at_noon(D))
        self.master()  # the attempt refreshed learner state; keep the project unlocked
        self.assertEqual(self.submit(self.stages[0]).status_code, 201)
        self.move(D)
        self.assertEqual(self.streak(), (1, 1))
