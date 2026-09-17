from datetime import timedelta

from django.test import SimpleTestCase

from apps.next_action import constants as c
from apps.next_action.candidates import (
    candidate_for,
    concept_started,
    deepen_reasons,
    is_course_complete,
    practice_urgency,
    rank_candidates,
    review_urgency,
)
from apps.next_action.prerequisites import (
    concept_prerequisites_ready,
    skill_prerequisites_ready,
)
from apps.next_action.tests.helpers import ALL_MODES, NOW, active, context


def candidate(**fields):
    return candidate_for(context(**fields), NOW)


class CandidateTierTests(SimpleTestCase):
    def test_tiers(self) -> None:
        cases = [
            ({"active_misconceptions": (active("off-by-one"),)}, c.REMEDIATE, c.REMEDIATE_TIER),
            ({"review_due_at": NOW - timedelta(days=1)}, c.REVIEW, c.REVIEW_TIER),
            ({"mastery": 40.0, "band": "weak"}, c.PRACTICE, c.STRENGTHEN_TIER),
            ({"started": False, "has_state": False, "mastery": 0.0}, c.LEARN, c.INTRODUCE_TIER),
            ({"mastery": 70.0}, c.PRACTICE, c.DEEPEN_TIER),
        ]
        for fields, action, tier in cases:
            with self.subTest(action=action, tier=tier):
                result = candidate(**fields)
                self.assertEqual((result.action_type, result.priority_tier), (action, tier))

    def test_primary_reasons(self) -> None:
        self.assertEqual(
            candidate(active_misconceptions=(active("x"),)).reason_codes[0],
            c.ACTIVE_MISCONCEPTION,
        )
        self.assertEqual(candidate(review_due_at=NOW).reason_codes, (c.REVIEW_DUE,))
        weak_due = candidate(review_due_at=NOW, mastery=30.0)
        self.assertEqual(weak_due.reason_codes, (c.REVIEW_DUE, c.BELOW_PROGRESSION_THRESHOLD))
        self.assertEqual(candidate(mastery=64.99).reason_codes, (c.BELOW_PROGRESSION_THRESHOLD,))
        self.assertEqual(
            candidate(started=False, has_state=False).reason_codes, (c.NEW_CONCEPT_READY,)
        )

    def test_watch_never_remediates(self) -> None:
        result = candidate(watch_codes=("off-by-one",), mastery=50.0)
        self.assertEqual(result.action_type, c.PRACTICE)
        self.assertIn(c.WATCH_MISCONCEPTION, result.reason_codes)
        self.assertEqual(result.misconception_codes, ("off-by-one",))
        plain = candidate(mastery=50.0)
        self.assertGreater(result.urgency_score, plain.urgency_score)

    def test_future_review_is_not_due(self) -> None:
        self.assertEqual(
            candidate(review_due_at=NOW + timedelta(seconds=1)).priority_tier, c.DEEPEN_TIER
        )
        self.assertEqual(candidate(review_due_at=NOW).priority_tier, c.REVIEW_TIER)

    def test_unstarted_concepts_need_readiness_and_exercises(self) -> None:
        fresh = {"started": False, "has_state": False, "mastery": 0.0}
        self.assertIsNone(candidate(**fresh, prerequisites_ready=False))
        self.assertIsNone(candidate(**fresh, available_modes=frozenset()))
        # Review dates or readiness never apply to unstarted concepts.
        self.assertEqual(
            candidate(**fresh, review_due_at=NOW - timedelta(days=1)).action_type, c.LEARN
        )

    def test_started_concepts_ignore_prerequisites(self) -> None:
        result = candidate(mastery=30.0, prerequisites_ready=False)
        self.assertEqual(result.priority_tier, c.STRENGTHEN_TIER)
        missing_state = candidate(has_state=False, mastery=0.0, band="not_started")
        self.assertEqual(missing_state.priority_tier, c.STRENGTHEN_TIER)
        self.assertTrue(concept_started(has_state=False, has_attempts=True))
        self.assertFalse(concept_started(has_state=False, has_attempts=False))

    def test_mastered_concept_without_reasons_has_no_candidate(self) -> None:
        self.assertIsNone(candidate(mastery=95.0, band="mastered"))

    def test_deepen_reasons(self) -> None:
        self.assertEqual(deepen_reasons(context()), [c.NOT_YET_MASTERED])
        gap = context(band="mastered", mode_success=frozenset({"recognise", "complete"}))
        self.assertEqual(deepen_reasons(gap), [c.ADVANCED_MODE_GAP])
        weak_mode = context(
            band="mastered", mode_performance={**dict.fromkeys(ALL_MODES, 90.0), "fix": 40.0}
        )
        self.assertEqual(deepen_reasons(weak_mode), [c.MODE_WEAKNESS])
        self.assertEqual(
            deepen_reasons(context(band="mastered", trend="falling")), [c.FALLING_TREND]
        )
        self.assertEqual(
            deepen_reasons(context(band="mastered", watch_codes=("x",))), [c.WATCH_MISCONCEPTION]
        )
        # Modes without exercises are never a gap.
        only_two = context(
            band="mastered",
            available_modes=frozenset({"complete", "create"}),
            mode_success=frozenset({"complete", "create"}),
        )
        self.assertEqual(deepen_reasons(only_two), [])


class UrgencyTests(SimpleTestCase):
    def test_falling_trend_raises_urgency_within_the_tier(self) -> None:
        stable = candidate(mastery=50.0)
        falling = candidate(mastery=50.0, trend="falling")
        self.assertEqual(stable.priority_tier, falling.priority_tier)
        self.assertGreater(falling.urgency_score, stable.urgency_score)
        self.assertIn(c.FALLING_TREND, falling.reason_codes)
        # A falling deepen candidate never becomes review or remediation.
        deepen = candidate(mastery=90.0, band="mastered", trend="falling")
        self.assertEqual(deepen.priority_tier, c.DEEPEN_TIER)

    def test_urgency_never_crosses_tiers(self) -> None:
        loud_deepen = candidate(
            concept_id=1,
            mastery=65.0,
            trend="falling",
            watch_codes=("a", "b"),
            is_most_recent=True,
            mode_success=frozenset(),
        )
        quiet_learn = candidate(concept_id=2, started=False, has_state=False, mastery=0.0)
        quiet_review = candidate(concept_id=3, review_due_at=NOW, mastery=99.0, retention=100.0)
        quiet_remediate = candidate(
            concept_id=4, active_misconceptions=(active("x", confidence=0.0),), mastery=100.0
        )
        self.assertGreater(loud_deepen.urgency_score, quiet_learn.urgency_score)
        ranked = rank_candidates([loud_deepen, quiet_learn, quiet_review, quiet_remediate])
        self.assertEqual([r.concept_id for r in ranked], [4, 3, 2, 1])

    def test_review_urgency_is_bounded(self) -> None:
        ancient = context(review_due_at=NOW - timedelta(days=5000), retention=0.0, mastery=0.0)
        self.assertLessEqual(review_urgency(ancient, NOW), 30 + 20 + 20 + 10 + 5)
        fresh = context(review_due_at=NOW, retention=95.0, mastery=95.0)
        self.assertLess(review_urgency(fresh, NOW), review_urgency(ancient, NOW))
        unknown = context(review_due_at=NOW, retention=None, mastery=95.0)
        self.assertEqual(review_urgency(unknown, NOW), 10 + 1.0)

    def test_weaker_concepts_are_more_urgent_to_strengthen(self) -> None:
        self.assertGreater(
            practice_urgency(context(mastery=10.0)), practice_urgency(context(mastery=60.0))
        )

    def test_continuity_is_a_small_bonus(self) -> None:
        recent = candidate(concept_id=9, mastery=50.0, is_most_recent=True)
        other = candidate(concept_id=1, mastery=50.0)
        self.assertEqual(recent.urgency_score - other.urgency_score, c.CONTINUITY_BONUS)
        weaker = candidate(concept_id=2, mastery=30.0)
        self.assertEqual(rank_candidates([recent, weaker])[0].concept_id, 2)

    def test_remediation_follows_confidence(self) -> None:
        strong = candidate(concept_id=2, active_misconceptions=(active("a", 90.0),))
        weak = candidate(concept_id=1, active_misconceptions=(active("b", 61.0),))
        self.assertEqual(rank_candidates([weak, strong])[0].concept_id, 2)
        codes = candidate(active_misconceptions=(active("a", 90.0), active("b", 70.0)))
        self.assertEqual(codes.misconception_codes, ("a", "b"))


class RankingTests(SimpleTestCase):
    def test_ties_follow_curriculum_order(self) -> None:
        learn = {"started": False, "has_state": False, "mastery": 0.0}
        later_skill = candidate(concept_id=1, skill_order=2, concept_order=1, **learn)
        later_concept = candidate(concept_id=2, skill_order=1, concept_order=2, **learn)
        first = candidate(concept_id=5, skill_order=1, concept_order=1, **learn)
        same_order = candidate(concept_id=3, skill_order=1, concept_order=1, **learn)
        ranked = rank_candidates([later_skill, later_concept, first, same_order])
        self.assertEqual([r.concept_id for r in ranked], [3, 5, 2, 1])
        self.assertEqual(ranked, rank_candidates(reversed(ranked)))


class CompletionTests(SimpleTestCase):
    def test_course_complete_rules(self) -> None:
        done = context(band="mastered", mastery=95.0)
        self.assertTrue(is_course_complete([done, done], NOW))
        self.assertTrue(is_course_complete([context(band="mastered", watch_codes=("x",))], NOW))
        self.assertFalse(is_course_complete([], NOW))
        self.assertFalse(is_course_complete([done, context()], NOW))
        self.assertFalse(
            is_course_complete([done, context(band="mastered", review_due_at=NOW)], NOW)
        )
        self.assertFalse(
            is_course_complete(
                [done, context(band="mastered", active_misconceptions=(active("x"),))], NOW
            )
        )
        self.assertFalse(is_course_complete([context(started=False, band="not_started")], NOW))


class PrerequisiteTests(SimpleTestCase):
    def test_concept_threshold(self) -> None:
        self.assertFalse(concept_prerequisites_ready([1], {1: 64.99}))
        self.assertTrue(concept_prerequisites_ready([1], {1: 65.0}))
        self.assertFalse(concept_prerequisites_ready([1, 2], {1: 90.0}))
        self.assertTrue(concept_prerequisites_ready([], {}))

    def test_skill_rule(self) -> None:
        concepts = {10: [1, 2], 11: []}
        self.assertTrue(skill_prerequisites_ready([10], concepts, {1: 65.0, 2: 80.0}))
        self.assertFalse(skill_prerequisites_ready([10], concepts, {1: 99.0, 2: 64.0}))
        self.assertFalse(skill_prerequisites_ready([10], concepts, {1: 99.0}))
        self.assertFalse(skill_prerequisites_ready([11], concepts, {}))
        self.assertFalse(skill_prerequisites_ready([12], concepts, {}))
        self.assertTrue(skill_prerequisites_ready([], concepts, {}))
