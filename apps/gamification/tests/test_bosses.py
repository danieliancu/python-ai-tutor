from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.curriculum.models import SkillPrerequisite
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.gamification.bosses import PYTHON_BOSSES, boss_exercise_ids, sync_bosses
from apps.gamification.models import BossChallenge, BossCompletion, XPEventType
from apps.gamification.tests.helpers import GamificationFixtures
from apps.next_action.engine import next_action_for_enrollment


class BossTests(GamificationFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.boss = BossChallenge.objects.create(exercise=self.mcq)

    def test_wrong_answer_does_not_complete(self) -> None:
        attempt = self.wrong_mcq()
        self.assertEqual(attempt.status, "incorrect")
        self.assertFalse(BossCompletion.objects.exists())
        self.assertEqual(self.events(), [])

    def test_correct_answer_completes_once(self) -> None:
        attempt = self.correct_mcq()
        self.assertEqual((attempt.status, attempt.is_correct, attempt.score), ("correct", True, 1))
        completion = BossCompletion.objects.get()
        self.assertEqual(
            (completion.enrollment, completion.boss, completion.attempt),
            (self.enrollment, self.boss, attempt),
        )
        self.assertIn((XPEventType.BOSS_COMPLETED, 100), self.events())
        self.assertIn((XPEventType.EXERCISE_COMPLETED, 20), self.events())
        self.correct_mcq()
        self.assertEqual(BossCompletion.objects.count(), 1)
        self.assertEqual(
            self.events(event_type=XPEventType.BOSS_COMPLETED), [("boss_completed", 100)]
        )
        self.assertEqual(self.profile.gamification.total_xp, 130)

    def test_custom_bonus(self) -> None:
        self.boss.bonus_xp = 150
        self.boss.save()
        self.correct_mcq()
        self.assertIn((XPEventType.BOSS_COMPLETED, 150), self.events())

    def test_inactive_boss_gives_no_bonus(self) -> None:
        self.boss.is_active = False
        self.boss.save()
        self.correct_mcq()
        self.assertFalse(BossCompletion.objects.exists())
        self.assertEqual(boss_exercise_ids(self.python_world.pk), [])

    def test_database_uniqueness(self) -> None:
        self.correct_mcq()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BossCompletion.objects.create(enrollment=self.enrollment, boss=self.boss)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BossChallenge.objects.create(exercise=self.mcq)


class BossProgressionTests(GamificationFixtures, TestCase):
    def test_a_boss_does_not_change_what_comes_next(self) -> None:
        world = self.python_world
        first_skill = self.mcq.lesson.concept.skill
        later_skill = make_skill(world, order=first_skill.order + 1)
        SkillPrerequisite.objects.create(skill=later_skill, prerequisite=first_skill)
        locked = make_exercise(
            make_lesson(make_concept(later_skill)),
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            evaluation_spec={"correct_option": "a"},
        )
        now = timezone.now()
        before = next_action_for_enrollment(self.enrollment, now=now)
        BossChallenge.objects.create(exercise=locked)
        after = next_action_for_enrollment(self.enrollment, now=now)
        self.assertEqual(before, after)
        self.assertNotEqual(after.exercise_id, locked.pk)

        # Answering the boss directly still goes through ordinary evaluation.
        attempt = self.record(locked, "b")
        self.assertEqual(attempt.status, "incorrect")
        self.assertFalse(BossCompletion.objects.exists())


class BossSeedTests(TestCase):
    def test_python_bosses_are_seeded_on_create_code_exercises(self) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        out = StringIO()
        call_command("seed_python_exercises", stdout=out)
        self.assertIn("Boss Challenges: 4 created", out.getvalue())
        bosses = BossChallenge.objects.select_related("exercise__lesson__concept__skill")
        self.assertEqual(
            [boss.exercise.slug for boss in bosses], [slug for slug, _ in PYTHON_BOSSES]
        )
        for boss in bosses:
            with self.subTest(boss=boss.exercise.slug):
                self.assertEqual(boss.exercise.learning_mode, LearningMode.CREATE)
                self.assertEqual(boss.exercise.response_type, ResponseType.CODE)
                self.assertEqual(boss.bonus_xp, 100)
        skill_orders = [boss.exercise.lesson.concept.skill.order for boss in bosses]
        self.assertEqual(skill_orders, sorted(set(skill_orders)))  # spread across the course

        call_command("seed_python_exercises", stdout=out)
        self.assertEqual(BossChallenge.objects.count(), 4)
        self.assertEqual(Exercise.objects.filter(boss__isnull=False).count(), 4)

    def test_sync_reports_missing_exercises(self) -> None:
        stats = sync_bosses("no-such-world")
        self.assertEqual(stats["missing"], [slug for slug, _ in PYTHON_BOSSES])
