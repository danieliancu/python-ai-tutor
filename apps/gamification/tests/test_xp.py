from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.curriculum.tests.helpers import make_concept
from apps.gamification.models import GamificationProfile, XPEvent, XPEventType
from apps.gamification.services import (
    sync_enrollment_exercise,
    sync_learner,
    sync_skill_mastery,
)
from apps.gamification.tests.helpers import GamificationFixtures

COMPLETED = (XPEventType.EXERCISE_COMPLETED, 20)
FIRST_TRY = (XPEventType.FIRST_TRY, 5)
INDEPENDENCE = (XPEventType.INDEPENDENCE, 5)


def total_xp(profile) -> int:
    return GamificationProfile.objects.get(learner=profile).total_xp


class ExerciseXPTests(GamificationFixtures, TestCase):
    def test_first_completion_on_first_try_unaided(self) -> None:
        attempt = self.correct_mcq()
        self.assertEqual(self.events(), [COMPLETED, FIRST_TRY, INDEPENDENCE])
        self.assertEqual(total_xp(self.profile), 30)
        self.assertEqual(set(XPEvent.objects.values_list("attempt", flat=True)), {attempt.pk})

    def test_repeating_a_correct_answer_earns_nothing_more(self) -> None:
        self.correct_mcq()
        self.correct_mcq()
        self.wrong_mcq()
        self.correct_mcq()
        self.assertEqual(self.events(), [COMPLETED, FIRST_TRY, INDEPENDENCE])
        self.assertEqual(total_xp(self.profile), 30)

    def test_no_first_try_bonus_after_a_wrong_answer(self) -> None:
        self.wrong_mcq()
        self.assertEqual(self.events(), [])
        second = self.correct_mcq()
        self.assertEqual(self.events(), [COMPLETED, INDEPENDENCE])
        self.assertEqual(
            XPEvent.objects.get(event_type=XPEventType.EXERCISE_COMPLETED).attempt, second
        )
        self.assertEqual(total_xp(self.profile), 25)

    def test_no_first_try_bonus_after_an_invalid_answer(self) -> None:
        self.record(self.mcq, 12)  # invalid
        self.correct_mcq()
        self.assertEqual(self.events(), [COMPLETED, INDEPENDENCE])

    def test_assistance_removes_only_the_independence_bonus(self) -> None:
        for help_used in ({"hint_level": 1}, {"used_explanation": True}, {"used_solution": True}):
            with self.subTest(help_used=help_used):
                XPEvent.objects.all().delete()
                ExerciseAttempt.objects.all().delete()
                self.correct_mcq(**help_used)
                self.assertEqual(self.events(), [COMPLETED, FIRST_TRY])

    def test_server_recorded_assistance_is_used(self) -> None:
        # The stored attempt fields are authoritative, whatever produced them.
        attempt = self.wrong_mcq()
        ExerciseAttempt.objects.filter(pk=attempt.pk).update(
            status=AttemptStatus.CORRECT, is_correct=True, score=1, used_solution=True
        )
        sync_enrollment_exercise(self.enrollment, self.mcq)
        self.assertEqual(self.events(), [COMPLETED, FIRST_TRY])

    def test_help_later_never_removes_earned_xp(self) -> None:
        self.correct_mcq()
        self.correct_mcq(used_solution=True, hint_level=3)
        self.assertEqual(total_xp(self.profile), 30)

    def test_unjudged_and_wrong_answers_earn_nothing(self) -> None:
        self.record(self.numeric, "about twelve")  # invalid
        self.record(self.code, "print('hi')")  # unsupported
        self.break_python_runner()
        with self.assertLogs("apps.attempts.services", level="ERROR"):
            self.record(self.code, "print('hi')")  # unavailable
        self.record(self.translation, "Hello")  # review required
        self.wrong_mcq()
        self.assertEqual(
            set(ExerciseAttempt.objects.values_list("status", flat=True)),
            {"invalid", "unsupported", "unavailable", "review_required", "incorrect"},
        )
        self.assertFalse(XPEvent.objects.exists())
        self.assertEqual(total_xp(self.profile), 0)

    def test_xp_is_platform_wide_and_keeps_its_course(self) -> None:
        self.correct_mcq()
        self.correct_numeric()
        self.assertEqual(total_xp(self.profile), 60)
        self.assertEqual(
            set(XPEvent.objects.values_list("world_id", "enrollment_id")),
            {
                (self.python_world.pk, self.enrollment.pk),
                (self.maths_world.pk, self.maths_enrollment.pk),
            },
        )


class SkillMasteryXPTests(GamificationFixtures, TestCase):
    def test_awarded_once_when_every_concept_is_mastered(self) -> None:
        skill = self.mcq.lesson.concept.skill
        self.assertEqual(sync_skill_mastery(self.enrollment, skill.pk), 0)
        self.master_skill(self.enrollment, skill)
        self.assertEqual(sync_skill_mastery(self.enrollment, skill.pk), 1)
        self.assertEqual(sync_skill_mastery(self.enrollment, skill.pk), 0)
        sync_learner(self.profile)
        self.assertEqual(self.events(), [(XPEventType.SKILL_MASTERED, 50)])
        self.assertEqual(total_xp(self.profile), 50)

    def test_partial_mastery_is_not_enough(self) -> None:
        skill = self.mcq.lesson.concept.skill
        self.master_skill(self.enrollment, skill)
        extra = make_concept(skill)
        self.assertEqual(sync_skill_mastery(self.enrollment, skill.pk), 0)
        extra.is_published = False
        extra.save()
        self.assertEqual(sync_skill_mastery(self.enrollment, skill.pk), 1)

    def test_xp_is_kept_if_mastery_later_declines(self) -> None:
        skill = self.mcq.lesson.concept.skill
        self.master_skill(self.enrollment, skill)
        sync_skill_mastery(self.enrollment, skill.pk)
        self.enrollment.concept_states.update(mastery_band="practising")
        sync_skill_mastery(self.enrollment, skill.pk)
        sync_learner(self.profile)
        self.assertEqual(total_xp(self.profile), 50)


class XPIntegrityTests(GamificationFixtures, TestCase):
    def test_database_rejects_duplicate_awards(self) -> None:
        self.correct_mcq()
        event = XPEvent.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            XPEvent.objects.create(
                learner=self.profile,
                world=self.python_world,
                event_type=event.event_type,
                xp=20,
                source_key=event.source_key,
            )

    def test_database_rejects_non_positive_xp(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            XPEvent.objects.create(
                learner=self.profile,
                world=self.python_world,
                event_type=XPEventType.EXERCISE_COMPLETED,
                xp=0,
                source_key="zero",
            )

    def test_a_concurrent_award_is_not_repeated(self) -> None:
        # Another request stored the award between our history read and our insert.
        attempt = self.wrong_mcq()
        ExerciseAttempt.objects.filter(pk=attempt.pk).update(
            status=AttemptStatus.CORRECT, is_correct=True, score=1
        )
        XPEvent.objects.create(
            learner=self.profile,
            world=self.python_world,
            enrollment=self.enrollment,
            event_type=XPEventType.EXERCISE_COMPLETED,
            xp=20,
            source_key=f"exercise:{self.mcq.pk}:completed",
        )
        created = sync_enrollment_exercise(self.enrollment, self.mcq)
        self.assertEqual(created, 2)  # only the bonuses
        self.assertEqual(
            XPEvent.objects.filter(event_type=XPEventType.EXERCISE_COMPLETED).count(), 1
        )

    def test_profile_total_is_recomputed_from_events(self) -> None:
        self.correct_mcq()
        GamificationProfile.objects.update(total_xp=9999)
        sync_learner(self.profile)
        self.assertEqual(total_xp(self.profile), 30)
