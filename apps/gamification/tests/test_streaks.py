from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase

from apps.gamification.models import GamificationProfile
from apps.gamification.selectors import header_stats
from apps.gamification.services import sync_learner
from apps.gamification.streaks import effective_streak, streak_from_days
from apps.gamification.tests.helpers import GamificationFixtures

D = date(2026, 3, 10)


def days(*offsets):
    return [D + timedelta(days=offset) for offset in offsets]


class StreakMathTests(SimpleTestCase):
    def test_consecutive_days(self) -> None:
        self.assertEqual(streak_from_days(days(0, 1, 2)), (3, 3, D + timedelta(days=2)))

    def test_repeated_days_count_once(self) -> None:
        self.assertEqual(streak_from_days(days(0, 0, 0, 1, 1)), (2, 2, D + timedelta(days=1)))

    def test_gap_resets_but_longest_is_kept(self) -> None:
        self.assertEqual(streak_from_days(days(0, 1, 2, 3, 6, 7)), (2, 4, D + timedelta(days=7)))

    def test_empty(self) -> None:
        self.assertEqual(streak_from_days([]), (0, 0, None))

    def test_effective_streak(self) -> None:
        self.assertEqual(effective_streak(4, D, D), 4)  # active today
        self.assertEqual(effective_streak(4, D, D + timedelta(days=1)), 4)  # until today ends
        self.assertEqual(effective_streak(4, D, D + timedelta(days=2)), 0)  # broken
        self.assertEqual(effective_streak(0, None, D), 0)


class StreakIntegrationTests(GamificationFixtures, TestCase):
    def test_streak_from_judged_attempts_across_courses(self) -> None:
        self.move_to(self.wrong_mcq(), D)  # a wrong answer is still learning
        self.move_to(self.correct_mcq(), D)  # same day: still one day
        self.move_to(self.correct_numeric(), D + timedelta(days=1))  # another course
        self.move_to(self.record(self.translation, "Hello"), D + timedelta(days=2))  # review
        sync_learner(self.profile)
        profile = GamificationProfile.objects.get(learner=self.profile)
        self.assertEqual(
            (profile.current_streak, profile.longest_streak, profile.last_activity_date),
            (3, 3, D + timedelta(days=2)),
        )
        self.assertEqual(header_stats(self.profile, today=D + timedelta(days=3))["streak_days"], 3)
        self.assertEqual(header_stats(self.profile, today=D + timedelta(days=4))["streak_days"], 0)

    def test_unjudged_attempts_do_not_count(self) -> None:
        self.move_to(self.record(self.numeric, "about twelve"), D)  # invalid
        self.move_to(self.record(self.code, "print('hi')"), D + timedelta(days=1))  # unsupported
        self.break_python_runner()
        with self.assertLogs("apps.attempts.services", level="ERROR"):
            unavailable = self.record(self.code, "print('hi')")
        self.move_to(unavailable, D + timedelta(days=2))
        sync_learner(self.profile)
        profile = GamificationProfile.objects.get(learner=self.profile)
        self.assertEqual((profile.current_streak, profile.longest_streak), (0, 0))
        self.assertIsNone(profile.last_activity_date)

    def test_gap_breaks_the_current_run(self) -> None:
        for offset in (0, 1, 2, 5):
            self.move_to(self.wrong_mcq(), D + timedelta(days=offset))
        sync_learner(self.profile)
        profile = GamificationProfile.objects.get(learner=self.profile)
        self.assertEqual((profile.current_streak, profile.longest_streak), (1, 3))
