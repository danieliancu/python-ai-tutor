from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.gamification import achievements as codes
from apps.gamification.models import (
    Achievement,
    AchievementAward,
    BossChallenge,
    BossCompletion,
    GamificationProfile,
    XPEvent,
)
from apps.gamification.tests.helpers import GamificationFixtures


class ProfilePageTests(GamificationFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_new_learner(self) -> None:
        response = self.client.get(reverse("learners:profile"))
        self.assertContains(response, "<dt>Level</dt><dd>1</dd>", html=False)
        self.assertContains(response, "<dt>Total XP</dt><dd>0</dd>", html=False)
        self.assertContains(response, "<dt>Current streak</dt><dd>0 days</dd>", html=False)
        self.assertContains(response, "Achievements · 0 of 7")
        self.assertContains(response, "No achievements yet.")
        self.assertContains(response, "Your profile · cursuri.net")

    def test_progress_and_achievements(self) -> None:
        self.correct_mcq()
        response = self.client.get(reverse("learners:profile"))
        self.assertContains(response, "<dt>Total XP</dt><dd>30</dd>", html=False)
        self.assertContains(response, "<dt>Current streak</dt><dd>1 day</dd>", html=False)
        self.assertContains(response, "<dt>Longest streak</dt><dd>1 day</dd>", html=False)
        self.assertContains(response, "Achievements · 2 of 7")
        self.assertContains(response, "First Step")
        self.assertContains(response, "Independent Thinker")
        self.assertContains(response, "status-badge--uncommon")

    def test_achievement_text_is_escaped(self) -> None:
        Achievement.objects.filter(code=codes.FIRST_STEP).update(
            title="<script>alert(1)</script>", description="<b>bold</b>"
        )
        self.correct_mcq()
        response = self.client.get(reverse("learners:profile"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertContains(response, "&lt;b&gt;bold&lt;/b&gt;")

    def test_bounded_queries(self) -> None:
        self.correct_mcq()
        self.correct_numeric()
        with self.assertNumQueries(7):
            self.client.get(reverse("learners:profile"))


class GamificationAdminTests(GamificationFixtures, TestCase):
    def test_pages_render(self) -> None:
        BossChallenge.objects.create(exercise=self.mcq)
        self.correct_mcq()
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        objects = {
            "gamificationprofile": GamificationProfile.objects.get(),
            "xpevent": XPEvent.objects.first(),
            "achievement": Achievement.objects.first(),
            "achievementaward": AchievementAward.objects.first(),
            "bosschallenge": BossChallenge.objects.get(),
            "bosscompletion": BossCompletion.objects.get(),
        }
        for name, obj in objects.items():
            for url in (
                reverse(f"admin:gamification_{name}_changelist"),
                reverse(f"admin:gamification_{name}_change", args=[obj.pk]),
            ):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:gamification_xpevent_add")).status_code, 403
        )
