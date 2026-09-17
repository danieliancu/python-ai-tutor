from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.exercises.tests.helpers import make_exercise
from apps.gamification import achievements as codes
from apps.gamification.models import Achievement, AchievementAward, BossChallenge
from apps.gamification.services import rebuild_gamification, sync_learner, sync_skill_mastery
from apps.gamification.tests.helpers import GamificationFixtures

D = date(2026, 4, 1)


class AchievementTests(GamificationFixtures, TestCase):
    def owned(self) -> set[str]:
        return set(
            AchievementAward.objects.filter(learner=self.profile).values_list(
                "achievement__code", flat=True
            )
        )

    def test_catalogue_is_seeded(self) -> None:
        self.assertEqual(
            list(Achievement.objects.values_list("code", flat=True)),
            [definition["code"] for definition in codes.ACHIEVEMENTS],
        )
        self.assertEqual(len(codes.ACHIEVEMENTS), 8)

    def test_first_step_and_independent_thinker(self) -> None:
        attempt = self.correct_mcq()
        self.assertEqual(self.owned(), {codes.FIRST_STEP, codes.INDEPENDENT_THINKER})
        award = AchievementAward.objects.get(achievement__code=codes.FIRST_STEP)
        self.assertEqual(
            (award.attempt, award.enrollment, award.world),
            (attempt, self.enrollment, self.python_world),
        )
        self.correct_numeric()
        self.assertEqual(AchievementAward.objects.count(), 2)

    def test_assisted_completion_is_not_independent(self) -> None:
        self.correct_mcq(hint_level=2)
        self.assertEqual(self.owned(), {codes.FIRST_STEP})

    def test_streak_achievements(self) -> None:
        for offset in range(3):
            self.move_to(self.wrong_mcq(), D + timedelta(days=offset))
        sync_learner(self.profile)
        self.assertEqual(self.owned(), {codes.ON_A_ROLL})
        for offset in range(3, 7):
            self.move_to(self.wrong_mcq(), D + timedelta(days=offset))
        sync_learner(self.profile)
        self.assertEqual(self.owned(), {codes.ON_A_ROLL, codes.CONSISTENT_LEARNER})
        # A broken streak never takes an achievement away.
        self.move_to(self.wrong_mcq(), D + timedelta(days=30))
        sync_learner(self.profile)
        self.assertEqual(self.owned(), {codes.ON_A_ROLL, codes.CONSISTENT_LEARNER})

    def test_skill_mastered(self) -> None:
        skill = self.mcq.lesson.concept.skill
        self.master_skill(self.enrollment, skill)
        sync_skill_mastery(self.enrollment, skill.pk)
        sync_learner(self.profile)
        self.assertEqual(self.owned(), {codes.SKILL_MASTERED})
        award = AchievementAward.objects.get()
        # Without a triggering attempt, the award belongs to the course where it was earned.
        self.assertEqual(
            (award.enrollment, award.world, award.attempt),
            (self.enrollment, self.python_world, None),
        )

    def test_boss_cleared(self) -> None:
        BossChallenge.objects.create(exercise=self.mcq)
        self.correct_mcq()
        self.assertIn(codes.BOSS_CLEARED, self.owned())

    def test_ten_down(self) -> None:
        lesson = self.mcq.lesson
        exercises = [
            make_exercise(
                lesson,
                response_type="multiple_choice",
                content={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
                evaluation_spec={"correct_option": "a"},
            )
            for _ in range(10)
        ]
        for exercise in exercises[:9]:
            self.record(exercise, "a")
        self.assertNotIn(codes.TEN_DOWN, self.owned())
        self.record(exercises[0], "a")  # the same exercise again doesn't count
        self.assertNotIn(codes.TEN_DOWN, self.owned())
        self.record(exercises[9], "a")
        self.assertIn(codes.TEN_DOWN, self.owned())

    def test_inactive_achievements_are_not_awarded(self) -> None:
        Achievement.objects.filter(code=codes.FIRST_STEP).update(is_active=False)
        self.correct_mcq()
        self.assertEqual(self.owned(), {codes.INDEPENDENT_THINKER})

    def test_awards_are_unique_and_survive_rebuilds(self) -> None:
        self.correct_mcq()
        before = list(AchievementAward.objects.order_by("id").values_list("id", "awarded_at"))
        rebuild_gamification()
        rebuild_gamification()
        after = list(AchievementAward.objects.order_by("id").values_list("id", "awarded_at"))
        self.assertEqual(before, after)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AchievementAward.objects.create(
                learner=self.profile, achievement=Achievement.objects.get(code=codes.FIRST_STEP)
            )
