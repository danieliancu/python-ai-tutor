from datetime import date, timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.gamification import achievements as codes
from apps.gamification.levels import level_for_xp
from apps.gamification.models import (
    AchievementAward,
    BossChallenge,
    BossCompletion,
    GamificationProfile,
    XPEvent,
)
from apps.gamification.services import refresh_for_attempt, sync_skill_mastery
from apps.gamification.tests.helpers import GamificationFixtures

D = date(2026, 5, 4)


class RebuildTests(GamificationFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        BossChallenge.objects.create(exercise=self.mcq)
        # History as it might exist from before Phase 9.
        self.move_to(self.wrong_mcq(), D)
        self.move_to(self.correct_mcq(), D + timedelta(days=1))  # +20 +5 +100
        self.move_to(self.correct_numeric(hint_level=1), D + timedelta(days=2))  # +20 +5
        self.move_to(self.record(self.code, "print('x')"), D + timedelta(days=5))  # unsupported
        self.master_skill(self.enrollment, self.mcq.lesson.concept.skill)  # +50
        self.wipe()

    def wipe(self) -> None:
        AchievementAward.objects.all().delete()
        XPEvent.objects.all().delete()
        BossCompletion.objects.all().delete()
        GamificationProfile.objects.all().delete()

    def run_command(self, *args) -> str:
        out = StringIO()
        call_command("rebuild_gamification", *args, stdout=out)
        return out.getvalue()

    def snapshot(self):
        profile = GamificationProfile.objects.get(learner=self.profile)
        return (
            profile.total_xp,
            level_for_xp(profile.total_xp),
            profile.current_streak,
            profile.longest_streak,
            profile.last_activity_date,
            sorted(XPEvent.objects.values_list("source_key", "xp")),
            BossCompletion.objects.count(),
            sorted(AchievementAward.objects.values_list("achievement__code", flat=True)),
        )

    def test_rebuild_reconstructs_everything(self) -> None:
        output = self.run_command()
        self.assertIn("Gamification rebuilt.", output)
        total, level, current, longest, last, events, bosses, awards = self.snapshot()
        self.assertEqual((total, level), (200, 2))
        self.assertEqual((current, longest, last), (3, 3, D + timedelta(days=2)))
        self.assertEqual(len(events), 6)
        self.assertEqual(bosses, 1)
        self.assertEqual(
            awards,
            sorted(
                [
                    codes.BOSS_CLEARED,
                    codes.FIRST_STEP,
                    codes.INDEPENDENT_THINKER,
                    codes.ON_A_ROLL,
                    codes.SKILL_MASTERED,
                ]
            ),
        )
        completion = BossCompletion.objects.get()
        self.assertEqual(completion.attempt.status, AttemptStatus.CORRECT)

    def test_rebuild_twice_is_identical(self) -> None:
        self.run_command()
        first = self.snapshot()
        output = self.run_command()
        self.assertIn("XP events created: 0; achievements awarded: 0", output)
        self.assertEqual(self.snapshot(), first)

    def test_filters(self) -> None:
        self.run_command("--enrollment-id", str(self.maths_enrollment.pk))
        self.assertEqual(
            set(XPEvent.objects.values_list("world_id", flat=True)),
            {self.maths_world.pk},
        )
        self.assertEqual(GamificationProfile.objects.get().total_xp, 25)
        self.run_command("--learner-id", str(self.profile.pk))
        self.assertEqual(GamificationProfile.objects.get().total_xp, 200)

    def test_unknown_ids(self) -> None:
        with self.assertRaisesMessage(CommandError, "Learner profile 999999"):
            self.run_command("--learner-id", "999999")
        with self.assertRaisesMessage(CommandError, "Enrollment 999999"):
            self.run_command("--enrollment-id", "999999")

    def test_live_and_rebuilt_totals_agree(self) -> None:
        self.run_command()
        rebuilt = self.snapshot()[0]
        self.wipe()
        # Replaying each attempt through the live step gives the same total.
        for attempt in ExerciseAttempt.objects.order_by("id"):
            refresh_for_attempt(attempt)
        sync_skill_mastery(self.enrollment, self.mcq.lesson.concept.skill_id)
        self.run_command()
        self.assertEqual(self.snapshot()[0], rebuilt)
