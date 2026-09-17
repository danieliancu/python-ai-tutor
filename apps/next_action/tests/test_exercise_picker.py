from django.test import SimpleTestCase, TestCase

from apps.curriculum.models import Lesson
from apps.curriculum.tests.helpers import make_lesson
from apps.exercises.models import LearningMode
from apps.next_action import constants as c
from apps.next_action.exercise_picker import choose_target_mode, pick_exercise
from apps.next_action.tests.helpers import ALL_MODES, WorldFixtures, context

R, C, F, X = (LearningMode.RECOGNISE, LearningMode.COMPLETE, LearningMode.FIX, LearningMode.CREATE)


class TargetModeTests(SimpleTestCase):
    def choose(self, available, success, performance=None, independence=None, action=c.PRACTICE):
        return choose_target_mode(available, success, performance or {}, independence or {}, action)

    def test_progression_through_modes(self) -> None:
        self.assertEqual(self.choose(ALL_MODES, []), R)
        self.assertEqual(self.choose(ALL_MODES, [R, C]), F)
        self.assertEqual(self.choose(ALL_MODES, [R, C, F]), X)
        self.assertEqual(self.choose(ALL_MODES, [C]), R)

    def test_all_succeeded_picks_the_weakest(self) -> None:
        performance = {R: 90.0, C: 70.0, F: 55.0, X: 80.0}
        self.assertEqual(self.choose(ALL_MODES, ALL_MODES, performance), F)
        tied = dict.fromkeys(ALL_MODES, 80.0)
        self.assertEqual(self.choose(ALL_MODES, ALL_MODES, tied), R)

    def test_review_also_weighs_independence(self) -> None:
        performance = {C: 80.0, X: 80.0}
        independence = {C: 90.0, X: 40.0}
        self.assertEqual(self.choose([C, X], [C, X], performance, independence, c.REVIEW), X)
        self.assertEqual(self.choose([C, X], [C, X], performance, independence, c.PRACTICE), C)

    def test_only_available_modes_are_considered(self) -> None:
        self.assertEqual(self.choose([X, C], []), C)
        self.assertEqual(self.choose([X, C], [C]), X)
        self.assertIsNone(self.choose([], []))


class PickerTests(WorldFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.lessons[self.a1.pk]
        self.base = self.ex[self.a1.pk]  # recognise, untagged

    def pick(self, exercises, action=c.PRACTICE, ctx=None, counts=None, recent=(), codes=()):
        return pick_exercise(
            exercises,
            action=action,
            context=ctx or context(mode_success=frozenset(), mode_performance={}),
            attempt_counts=counts or {},
            recent_ids=recent,
            active_codes=codes,
        )

    def test_target_mode_is_preferred(self) -> None:
        fix = self.exercise(self.a1, F)
        succeeded = context(mode_success=frozenset({R}), mode_performance={R: 90.0})
        result = self.pick([self.base, fix], ctx=succeeded)
        self.assertEqual((result.exercise, result.target_mode), (fix, F))
        self.assertEqual(self.pick([self.base, fix]).exercise, self.base)

    def test_remediation_prefers_tagged_exercises(self) -> None:
        tagged = self.exercise(self.a1, X, tags=["off-by-one"])
        result = self.pick([self.base, tagged], action=c.REMEDIATE, codes=("off-by-one",))
        self.assertEqual(result.exercise, tagged)
        self.assertFalse(result.remediation_fallback)

    def test_remediation_prefers_primary_and_broader_coverage(self) -> None:
        secondary = self.exercise(self.a1, R, tags=["loop-condition"])
        both = self.exercise(self.a1, R, tags=["loop-condition", "off-by-one"])
        primary = self.exercise(self.a1, R, tags=["off-by-one"])
        codes = ("off-by-one", "loop-condition")
        self.assertEqual(
            self.pick([secondary, primary, both], action=c.REMEDIATE, codes=codes).exercise, both
        )
        self.assertEqual(
            self.pick([secondary, primary], action=c.REMEDIATE, codes=codes).exercise, primary
        )

    def test_remediation_avoids_the_previous_exercise(self) -> None:
        first = self.exercise(self.a1, R, tags=["off-by-one"])
        second = self.exercise(self.a1, R, tags=["off-by-one"])
        result = self.pick(
            [first, second], action=c.REMEDIATE, codes=("off-by-one",), recent=[first.pk]
        )
        self.assertEqual(result.exercise, second)
        # Tag match still beats freshness.
        result = self.pick(
            [first, self.base], action=c.REMEDIATE, codes=("off-by-one",), recent=[first.pk]
        )
        self.assertEqual(result.exercise, first)

    def test_remediation_fallback(self) -> None:
        other = self.exercise(self.a1, C)
        result = self.pick([self.base, other], action=c.REMEDIATE, codes=("off-by-one",))
        self.assertTrue(result.remediation_fallback)
        self.assertEqual(result.exercise, self.base)

    def test_repeat_avoidance(self) -> None:
        a, b, cc, d = self.base, *(self.exercise(self.a1, R) for _ in range(3))
        self.assertEqual(self.pick([a, b, cc, d], recent=[a.pk, b.pk, cc.pk]).exercise, d)
        self.assertEqual(self.pick([a], recent=[a.pk]).exercise, a)

    def test_unattempted_then_fewer_attempts(self) -> None:
        tried = self.base
        fresh = self.exercise(self.a1, R)
        self.assertEqual(self.pick([tried, fresh], counts={tried.pk: 3}).exercise, fresh)
        once = self.exercise(self.a1, R)
        self.assertEqual(self.pick([tried, once], counts={tried.pk: 3, once.pk: 1}).exercise, once)
        # A target-mode match still outranks freshness.
        fix_fresh = self.exercise(self.a1, F)
        self.assertEqual(self.pick([tried, fix_fresh], counts={tried.pk: 3}).exercise, tried)

    def test_lesson_kind_preferences(self) -> None:
        review_lesson = make_lesson(self.a1, kind=Lesson.Kind.REVIEW)
        practice_lesson = make_lesson(self.a1, kind=Lesson.Kind.PRACTICE)
        in_review = self.exercise(self.a1, R, lesson=review_lesson)
        in_practice = self.exercise(self.a1, R, lesson=practice_lesson)
        pool = [self.base, in_review, in_practice]
        self.assertEqual(self.pick(pool, action=c.LEARN).exercise, self.base)
        self.assertEqual(self.pick(pool, action=c.PRACTICE).exercise, in_practice)
        self.assertEqual(self.pick(pool, action=c.REVIEW).exercise, in_review)
        self.assertEqual(self.pick(pool, action=c.REMEDIATE).exercise, in_practice)

    def test_deterministic_authored_order(self) -> None:
        later = self.exercise(self.a1, R)
        self.assertEqual(self.pick([later, self.base]).exercise, self.base)
        self.assertEqual(self.pick([self.base, later]).exercise, self.base)
        self.assertIsNone(self.pick([]))
