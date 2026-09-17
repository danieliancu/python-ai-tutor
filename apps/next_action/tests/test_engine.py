from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.curriculum.models import Concept, Lesson, Skill
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill, make_world
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learners.models import Enrollment
from apps.next_action import constants as c
from apps.next_action.engine import _load, next_action_for_enrollment
from apps.next_action.tests.helpers import NOW, WorldFixtures, choice

R, C, F, X = (LearningMode.RECOGNISE, LearningMode.COMPLETE, LearningMode.FIX, LearningMode.CREATE)


class EngineTests(WorldFixtures, TestCase):
    def decide(self, enrollment=None, now=NOW):
        return next_action_for_enrollment(enrollment or self.enrollment, now=now)

    def assertDecision(self, decision, action, concept=None, reason=None) -> None:
        self.assertEqual(decision.action_type, action)
        if concept is not None:
            self.assertEqual(decision.concept_id, concept.pk)
        if reason is not None:
            self.assertEqual(decision.primary_reason, reason)

    def ready(self, concept) -> bool:
        contexts = {ctx.concept_id: ctx for ctx in _load(self.enrollment).contexts}
        return contexts[concept.pk].prerequisites_ready

    # --- progression ---------------------------------------------------------------------

    def test_fresh_learner_learns_the_first_concept(self) -> None:
        decision = self.decide()
        self.assertDecision(decision, c.LEARN, self.a1, c.NEW_CONCEPT_READY)
        self.assertEqual(decision.exercise_id, self.ex[self.a1.pk].pk)
        self.assertEqual(decision.lesson_id, self.lessons[self.a1.pk].pk)
        self.assertEqual(decision.skill_id, self.skill_a.pk)
        self.assertEqual(decision.target_learning_mode, R)
        self.assertEqual(decision.algorithm_version, c.NEXT_ACTION_ALGORITHM_VERSION)
        self.assertEqual(decision.generated_at, NOW)

    def test_weak_started_concept_is_strengthened_before_new_content(self) -> None:
        self.state(self.a1, 40.0)
        self.assertDecision(self.decide(), c.PRACTICE, self.a1, c.BELOW_PROGRESSION_THRESHOLD)

    def test_basic_competence_unlocks_new_content(self) -> None:
        self.state(self.a1, 65.0)
        self.assertDecision(self.decide(), c.LEARN, self.a2, c.NEW_CONCEPT_READY)

    def test_concept_prerequisite_threshold(self) -> None:
        self.requires(self.a2, self.a1)
        state = self.state(self.a1, 64.99)
        self.assertFalse(self.ready(self.a2))
        self.assertTrue(self.ready(self.b1))
        self.assertDecision(self.decide(), c.PRACTICE, self.a1)
        state.mastery_score = 65
        state.save()
        self.assertTrue(self.ready(self.a2))
        self.assertDecision(self.decide(), c.LEARN, self.a2)

    def test_skill_prerequisites_cover_every_published_concept(self) -> None:
        self.skill_requires(self.skill_b, self.skill_a)
        self.state(self.a1, 95.0, band="mastered")
        self.assertFalse(self.ready(self.b1))  # a2 never started
        self.assertDecision(self.decide(), c.LEARN, self.a2)
        weak = self.state(self.a2, 64.0)
        self.assertFalse(self.ready(self.b1))
        self.assertDecision(self.decide(), c.PRACTICE, self.a2)
        weak.mastery_score = 70
        weak.save()
        self.assertTrue(self.ready(self.b1))
        self.assertDecision(self.decide(), c.LEARN, self.b1)
        # An unpublished concept in the prerequisite skill does not block.
        make_concept(self.skill_a, is_published=False)
        self.assertTrue(self.ready(self.b1))

    def test_unpublished_prerequisite_skill_blocks(self) -> None:
        self.skill_requires(self.skill_b, self.skill_a)
        self.state(self.a1, 95.0, band="mastered")
        self.state(self.a2, 95.0, band="mastered")
        self.assertTrue(self.ready(self.b1))
        self.skill_a.is_published = False
        self.skill_a.save()
        self.assertFalse(self.ready(self.b1))

    def test_started_concepts_stay_available(self) -> None:
        self.requires(self.b1, self.a1)
        self.state(self.a1, 50.0)
        self.state(self.b1, 30.0)
        self.assertFalse(self.ready(self.b1))
        self.assertDecision(self.decide(), c.PRACTICE, self.b1)

    def test_attempt_without_derived_state_counts_as_started(self) -> None:
        self.attempt(self.ex[self.b1.pk])
        decision = self.decide()
        self.assertDecision(decision, c.PRACTICE, self.b1, c.BELOW_PROGRESSION_THRESHOLD)
        self.assertNotEqual(decision.action_type, c.LEARN)

    # --- priorities ----------------------------------------------------------------------

    def test_active_misconception_beats_new_content(self) -> None:
        self.state(self.a1, 70.0)
        self.misconception(self.a1, "range-exclusive-stop")
        decision = self.decide()
        self.assertDecision(decision, c.REMEDIATE, self.a1, c.ACTIVE_MISCONCEPTION)
        self.assertEqual(decision.misconception_codes, ("range-exclusive-stop",))
        self.assertIn(c.REMEDIATION_FALLBACK, decision.reason_codes)

    def test_watch_does_not_force_remediation(self) -> None:
        self.state(self.a1, 70.0)
        self.misconception(self.a1, "off-by-one", status="watch")
        self.misconception(self.a1, "old-idea", status="resolved")
        self.assertDecision(self.decide(), c.LEARN, self.a2)

    def test_due_review_beats_new_content(self) -> None:
        self.state(self.a1, 70.0, review_due_at=NOW - timedelta(hours=1))
        self.assertDecision(self.decide(), c.REVIEW, self.a1, c.REVIEW_DUE)
        self.assertDecision(self.decide(now=NOW - timedelta(hours=2)), c.LEARN, self.a2)

    def test_active_misconception_beats_due_review(self) -> None:
        self.state(self.a1, 70.0, review_due_at=NOW - timedelta(days=10))
        self.state(self.a2, 90.0)
        self.misconception(self.a2, "off-by-one", confidence=61.0)
        self.assertDecision(self.decide(), c.REMEDIATE, self.a2)

    def test_most_confident_misconception_is_remediated_first(self) -> None:
        self.state(self.a1, 70.0)
        self.state(self.a2, 70.0)
        self.misconception(self.a1, "one", confidence=62.0)
        self.misconception(self.a2, "two", confidence=62.0)
        self.misconception(self.a2, "three", confidence=88.0)
        decision = self.decide()
        self.assertDecision(decision, c.REMEDIATE, self.a2)
        self.assertEqual(decision.misconception_codes, ("three", "two"))

    def test_remediation_uses_tagged_exercise_and_target_mode(self) -> None:
        tagged = self.exercise(self.a1, F, tags=["off-by-one"])
        self.state(self.a1, 70.0, modes={R: (90.0, 3)})
        self.misconception(self.a1, "off-by-one")
        decision = self.decide()
        self.assertEqual((decision.exercise_id, decision.target_learning_mode), (tagged.pk, F))
        self.assertNotIn(c.REMEDIATION_FALLBACK, decision.reason_codes)

    def test_target_mode_follows_evidence(self) -> None:
        for mode in (C, F, X):
            self.exercise(self.a1, mode)
        self.state(self.a1, 60.0, modes={R: (90.0, 2), C: (80.0, 1)})
        decision = self.decide()
        self.assertEqual((decision.action_type, decision.target_learning_mode), (c.PRACTICE, F))

    def test_deepening_after_new_content_is_exhausted(self) -> None:
        self.state(self.a1, 70.0)
        self.state(self.a2, 95.0, band="mastered", modes={R: (95.0, 3)})
        self.state(self.b1, 95.0, band="mastered", modes={R: (95.0, 3)})
        decision = self.decide()
        self.assertDecision(decision, c.PRACTICE, self.a1, c.NOT_YET_MASTERED)

    def test_falling_trend_raises_priority_within_a_tier(self) -> None:
        self.state(self.a1, 50.0)
        self.state(self.a2, 50.0, trend="falling")
        decision = self.decide()
        self.assertDecision(decision, c.PRACTICE, self.a2)
        self.assertIn(c.FALLING_TREND, decision.reason_codes)

    # --- completion and dead ends -------------------------------------------------------

    def master_everything(self):
        return [
            self.state(concept, 95.0, band="mastered", modes={R: (95.0, 3)})
            for concept in (self.a1, self.a2, self.b1)
        ]

    def test_course_complete(self) -> None:
        self.master_everything()
        self.misconception(self.b1, "still-watching", status="watch")
        decision = self.decide()
        self.assertDecision(decision, c.COURSE_COMPLETE, reason=c.WORLD_COMPLETE)
        self.assertIsNone(decision.concept_id)
        self.assertIsNone(decision.lesson_id)
        self.assertIsNone(decision.exercise_id)
        self.assertIsNone(decision.target_learning_mode)

    def test_mastered_but_review_due_is_not_complete(self) -> None:
        states = self.master_everything()
        states[1].review_due_at = NOW - timedelta(days=1)
        states[1].save()
        self.assertDecision(self.decide(), c.REVIEW, self.a2)

    def test_mastered_but_active_misconception_is_not_complete(self) -> None:
        self.master_everything()
        self.misconception(self.b1, "off-by-one")
        self.assertDecision(self.decide(), c.REMEDIATE, self.b1)

    def test_blocked_is_not_complete(self) -> None:
        locked = make_concept(self.skill_a, is_published=False)
        self.requires(self.a2, locked)
        self.requires(self.b1, locked)
        self.state(self.a1, 95.0, band="mastered", modes={R: (95.0, 3)})
        decision = self.decide()
        self.assertDecision(decision, c.NO_AVAILABLE_ACTION, reason=c.BLOCKED_BY_PREREQUISITES)
        self.assertIsNone(decision.exercise_id)

    def test_authoring_gap(self) -> None:
        self.state(self.a1, 95.0, band="mastered", modes={R: (95.0, 3)})
        Exercise.objects.filter(lesson__concept__in=[self.a2, self.b1]).update(is_published=False)
        decision = self.decide()
        self.assertDecision(decision, c.NO_AVAILABLE_ACTION, reason=c.NO_PUBLISHED_EXERCISE)
        # A started concept without exercises is skipped, never faked.
        self.state(self.a2, 30.0)
        self.assertDecision(self.decide(), c.NO_AVAILABLE_ACTION, reason=c.NO_PUBLISHED_EXERCISE)

    def test_world_without_content(self) -> None:
        empty = make_world("Empty World")
        enrollment = Enrollment.objects.create(learner=self.profile, world=empty)
        make_concept(make_skill(empty), is_published=False)
        decision = self.decide(enrollment)
        self.assertDecision(decision, c.NO_AVAILABLE_ACTION, reason=c.NO_PUBLISHED_CONTENT)

    def test_unpublished_content_is_never_returned(self) -> None:
        cases = [
            ("exercise", lambda: Exercise.objects.filter(pk=self.ex[self.a1.pk].pk)),
            ("lesson", lambda: Lesson.objects.filter(pk=self.lessons[self.a1.pk].pk)),
            ("concept", lambda: Concept.objects.filter(pk=self.a1.pk)),
            ("skill", lambda: Skill.objects.filter(pk=self.skill_a.pk)),
        ]
        for label, queryset in cases:
            with self.subTest(level=label):
                queryset().update(is_published=False)
                decision = self.decide()
                self.assertNotEqual(decision.exercise_id, self.ex[self.a1.pk].pk)
                self.assertTrue(
                    Exercise.objects.filter(pk=decision.exercise_id, is_published=True).exists()
                )
                queryset().update(is_published=True)

    def test_repeated_exercise_is_avoided(self) -> None:
        second = self.exercise(self.a1, R)
        self.attempt(self.ex[self.a1.pk])
        self.state(self.a1, 40.0)
        self.assertEqual(self.decide().exercise_id, second.pk)

    # --- determinism and isolation -------------------------------------------------------

    def test_decisions_are_deterministic(self) -> None:
        self.state(self.a1, 50.0)
        self.state(self.a2, 50.0)
        self.state(self.b1, 50.0)
        decisions = {self.decide() for _ in range(5)}
        self.assertEqual(len(decisions), 1)
        self.assertDecision(decisions.pop(), c.PRACTICE, self.a1)

    def test_learners_are_isolated(self) -> None:
        other = self.other_learner()
        self.state(self.a1, 30.0, enrollment=other)
        self.misconception(self.a1, "off-by-one", enrollment=other)
        self.state(self.a1, 95.0, band="mastered", modes={R: (95.0, 3)})
        self.assertDecision(self.decide(), c.LEARN, self.a2)
        self.assertDecision(self.decide(other), c.REMEDIATE, self.a1)

    def test_worlds_are_isolated(self) -> None:
        maths_world = make_world("Maths World")
        maths_skill = make_skill(maths_world)
        maths_concept = make_concept(maths_skill)
        maths_exercise = make_exercise(
            make_lesson(maths_concept),
            response_type=ResponseType.NUMERIC,
            learning_mode=LearningMode.CREATE,
            evaluation_spec={"expected": 5, "tolerance": 0, "misconceptions": ["sign-error"]},
        )
        maths = Enrollment.objects.create(learner=self.profile, world=maths_world)
        self.state(maths_concept, 20.0, enrollment=maths)
        self.misconception(maths_concept, "sign-error", enrollment=maths)
        self.attempt(maths_exercise, enrollment=maths, at=NOW)

        python_decision = self.decide()
        self.assertDecision(python_decision, c.LEARN, self.a1)
        self.assertEqual(python_decision.world_id, self.world.pk)

        maths_decision = self.decide(maths)
        self.assertDecision(maths_decision, c.REMEDIATE, maths_concept)
        self.assertEqual(maths_decision.exercise_id, maths_exercise.pk)
        self.assertEqual(maths_decision.target_learning_mode, LearningMode.CREATE)

    def test_query_count_does_not_grow_with_the_curriculum(self) -> None:
        self.state(self.a1, 50.0, modes={R: (50.0, 1)})
        self.misconception(self.a2, "off-by-one", status="watch")
        with CaptureQueriesContext(connection) as small:
            self.decide()
        for index in range(10):
            concept = make_concept(self.skill_b)
            lesson = make_lesson(concept)
            make_exercise(lesson, learning_mode=R, **choice())
            if index % 2:
                self.state(concept, 40.0 + index, modes={R: (40.0, 1)})
                self.requires(concept, self.a2)
        with CaptureQueriesContext(connection) as large:
            self.decide()
        self.assertEqual(len(small), len(large))
        self.assertLessEqual(len(large), 12)
