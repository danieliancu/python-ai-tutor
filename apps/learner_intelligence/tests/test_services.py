from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.test import TestCase

from apps.accounts.tests.helpers import make_user
from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.curriculum.tests.helpers import make_concept
from apps.exercises.models import Exercise, LearningMode
from apps.learner_intelligence import selectors
from apps.learner_intelligence.models import ConceptModeState, ConceptState
from apps.learner_intelligence.scoring import ALGORITHM_VERSION
from apps.learner_intelligence.services import refresh_concept_state, refresh_for_attempt
from apps.learner_intelligence.tests.helpers import (
    BASE_TIME,
    CORRECT,
    INCORRECT,
    IntelligenceFixtures,
)
from apps.learners.models import Enrollment, LearnerProfile

RECOGNISE = LearningMode.RECOGNISE
COMPLETE = LearningMode.COMPLETE
FIX = LearningMode.FIX
CREATE = LearningMode.CREATE


def snapshot(state: ConceptState) -> dict:
    state.refresh_from_db()
    modes = [model_to_dict(row) | {"updated_at": row.updated_at} for row in state.mode_states.all()]
    return model_to_dict(state) | {"updated_at": state.updated_at, "modes": modes}


class RefreshTests(IntelligenceFixtures, TestCase):
    def attempts(self, mode, pattern: str, start_minutes: int = 0, **fields) -> None:
        for index, char in enumerate(pattern):
            self.make_attempt(
                self.by_mode[mode],
                CORRECT if char == "1" else INCORRECT,
                at=BASE_TIME + timedelta(minutes=start_minutes + index),
                **fields,
            )

    def refresh(self, enrollment=None, concept=None) -> ConceptState:
        return refresh_concept_state(enrollment or self.enrollment, concept or self.concept)

    def test_refresh_creates_state_from_attempts(self) -> None:
        self.attempts(FIX, "111")
        state = self.refresh()
        self.assertEqual(state.mastery_score, Decimal("90.00"))
        self.assertEqual(state.mastery_band, "mastered")
        self.assertEqual(state.evidence_count, 3)
        self.assertEqual(state.correct_count, 3)
        self.assertEqual(state.independence_score, Decimal("100.00"))
        self.assertIsNone(state.retention_score)
        self.assertEqual(state.trend, "insufficient_data")
        self.assertEqual(state.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(ConceptState.objects.count(), 1)

    def test_activity_timestamps_and_review_date(self) -> None:
        success = self.make_attempt(self.by_mode[COMPLETE], CORRECT, at=BASE_TIME)
        failure = self.make_attempt(
            self.by_mode[COMPLETE], INCORRECT, at=BASE_TIME + timedelta(hours=1)
        )
        latest = self.make_attempt(
            self.by_mode[COMPLETE],
            AttemptStatus.UNAVAILABLE,
            at=BASE_TIME + timedelta(hours=2),
        )
        state = self.refresh()
        self.assertEqual(state.last_attempt_at, latest.submitted_at)
        self.assertEqual(state.last_success_at, success.submitted_at)
        self.assertEqual(
            state.review_due_at, failure.submitted_at + timedelta(days=state.stability_days)
        )

    def test_non_judged_attempts_do_not_damage_mastery(self) -> None:
        self.attempts(FIX, "111")
        before = self.refresh()
        mastery, evidence = before.mastery_score, before.evidence_count
        for index, status in enumerate(
            [
                AttemptStatus.UNSUPPORTED,
                AttemptStatus.UNAVAILABLE,
                AttemptStatus.REVIEW_REQUIRED,
                AttemptStatus.INVALID,
            ]
        ):
            self.make_attempt(
                self.by_mode[FIX], status, at=BASE_TIME + timedelta(minutes=30 + index)
            )
        after = self.refresh()
        self.assertEqual(after.mastery_score, mastery)
        self.assertEqual(after.evidence_count, evidence)
        self.assertEqual(after.mode_states.get().attempt_count, 3)
        self.assertEqual(after.last_attempt_at, BASE_TIME + timedelta(minutes=33))

    def test_only_non_judged_history_is_not_started(self) -> None:
        self.make_attempt(self.by_mode[FIX], AttemptStatus.UNSUPPORTED, at=BASE_TIME)
        state = self.refresh()
        self.assertEqual(state.mastery_band, "not_started")
        self.assertEqual(state.mastery_score, Decimal("0"))
        self.assertIsNone(state.review_due_at)
        self.assertIsNone(state.independence_score)
        self.assertEqual(state.mode_states.count(), 0)
        self.assertEqual(state.last_attempt_at, BASE_TIME)

    def test_incorrect_attempts_lower_stored_mastery(self) -> None:
        self.attempts(CREATE, "111")
        strong = self.refresh().mastery_score
        self.attempts(CREATE, "xx", start_minutes=10)
        self.assertLess(self.refresh().mastery_score, strong)

    def test_mode_states_use_only_their_own_attempts(self) -> None:
        self.attempts(RECOGNISE, "111")
        self.attempts(COMPLETE, "1x", start_minutes=10)
        self.attempts(CREATE, "xxx", start_minutes=20)
        state = self.refresh()
        modes = {row.learning_mode: row for row in state.mode_states.all()}
        self.assertEqual(set(modes), {RECOGNISE, COMPLETE, CREATE})
        self.assertEqual(modes[RECOGNISE].performance_score, Decimal("100.00"))
        self.assertEqual(modes[CREATE].performance_score, Decimal("0.00"))
        self.assertEqual((modes[COMPLETE].attempt_count, modes[COMPLETE].correct_count), (2, 1))
        self.assertEqual(modes[CREATE].last_attempt_at, BASE_TIME + timedelta(minutes=22))
        self.assertLess(modes[COMPLETE].performance_score, Decimal("100"))

        self.attempts(FIX, "1", start_minutes=30)
        self.assertEqual(self.refresh().mode_states.count(), 4)

    def test_stale_mode_rows_are_removed(self) -> None:
        self.attempts(CREATE, "111")
        state = self.refresh()
        self.assertEqual(list(state.mode_states.values_list("learning_mode", flat=True)), [CREATE])
        # The exercise is re-classified; state follows the attempt history's current meaning.
        Exercise.objects.filter(pk=self.by_mode[CREATE].pk).update(learning_mode=COMPLETE)
        state = self.refresh()
        self.assertEqual(
            list(state.mode_states.values_list("learning_mode", flat=True)), [COMPLETE]
        )
        self.assertEqual(state.mastery_score, Decimal("80.00"))

    def test_refresh_is_idempotent(self) -> None:
        self.attempts(COMPLETE, "1x1")
        self.attempts(FIX, "11", start_minutes=3 * 24 * 60, duration_seconds=90, hint_level=1)
        first = snapshot(self.refresh())
        second = snapshot(self.refresh())
        self.assertEqual(first, second)
        self.assertEqual(ConceptState.objects.count(), 1)
        self.assertEqual(ConceptModeState.objects.count(), 2)

    def test_refresh_for_attempt_resolves_enrollment_and_concept(self) -> None:
        attempt = self.make_attempt(self.by_mode[FIX], CORRECT)
        state = refresh_for_attempt(attempt)
        self.assertEqual((state.enrollment, state.concept), (self.enrollment, self.concept))

    def test_no_history_means_no_state(self) -> None:
        self.assertIsNone(self.refresh())
        attempt = self.make_attempt(self.by_mode[FIX], CORRECT)
        self.refresh()
        # History moves elsewhere (e.g. the attempt is reassigned by an admin fix-up).
        ExerciseAttempt.objects.filter(pk=attempt.pk).update(exercise=self.translation)
        self.assertIsNone(self.refresh())
        self.assertFalse(ConceptState.objects.filter(concept=self.concept).exists())

    def test_one_state_per_enrollment_and_concept(self) -> None:
        self.make_attempt(self.by_mode[FIX], CORRECT)
        self.refresh()
        self.refresh()
        self.assertEqual(ConceptState.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConceptState.objects.bulk_create(
                [ConceptState(enrollment=self.enrollment, concept=self.concept)]
            )

    def test_enrollments_remain_separate(self) -> None:
        self.attempts(CREATE, "xxx")
        python_before = snapshot(self.refresh())
        for index in range(5):
            self.make_attempt(
                self.translation,
                CORRECT,
                enrollment=self.english_enrollment,
                at=BASE_TIME + timedelta(minutes=index),
            )
        english = self.refresh(self.english_enrollment, self.english_concept)
        self.assertEqual(english.mastery_score, Decimal("100.00"))
        self.assertEqual(snapshot(self.refresh()), python_before)
        self.assertEqual(python_before["mastery_score"], Decimal("0.00"))
        self.assertIsNone(refresh_concept_state(self.maths_enrollment, self.maths_concept))
        self.assertEqual(ConceptState.objects.count(), 2)

    def test_learners_remain_independent(self) -> None:
        other = make_user("other")
        other_enrollment = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=other), world=self.python_world
        )
        self.attempts(CREATE, "111")
        for index in range(3):
            self.make_attempt(
                self.by_mode[CREATE],
                INCORRECT,
                enrollment=other_enrollment,
                at=BASE_TIME + timedelta(minutes=index),
            )
        mine = self.refresh()
        theirs = self.refresh(other_enrollment)
        self.assertEqual(mine.mastery_score, Decimal("100.00"))
        self.assertEqual(theirs.mastery_score, Decimal("0.00"))
        self.assertEqual(mine.mode_states.get().attempt_count, 3)
        self.assertEqual(theirs.mode_states.get().correct_count, 0)


class SelectorTests(IntelligenceFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.make_attempt(self.by_mode[FIX], INCORRECT, at=BASE_TIME)
        self.weak = refresh_concept_state(self.enrollment, self.concept)
        for index in range(3):
            self.make_attempt(
                self.translation,
                CORRECT,
                enrollment=self.english_enrollment,
                at=BASE_TIME + timedelta(minutes=index),
            )
        self.mastered = refresh_concept_state(self.english_enrollment, self.english_concept)

    def test_band_selectors(self) -> None:
        self.assertEqual(list(selectors.weak_concepts(self.enrollment)), [self.weak])
        self.assertEqual(list(selectors.mastered_concepts(self.enrollment)), [])
        self.assertEqual(
            list(selectors.mastered_concepts(self.english_enrollment)), [self.mastered]
        )
        self.assertEqual(selectors.concept_state_for(self.enrollment, self.concept), self.weak)
        self.assertIsNone(selectors.concept_state_for(self.enrollment, self.english_concept))

    def test_review_due_is_derived_from_now(self) -> None:
        due_at = self.mastered.review_due_at
        self.assertEqual(self.mastered.stability_days, 30)
        before, after = due_at - timedelta(seconds=1), due_at + timedelta(seconds=1)
        self.assertFalse(selectors.is_review_due(self.mastered, before))
        self.assertTrue(selectors.is_review_due(self.mastered, after))
        self.assertFalse(selectors.review_due_states(self.english_enrollment, before).exists())
        self.assertTrue(selectors.review_due_states(self.english_enrollment, after).exists())
        self.assertEqual(list(selectors.review_due_states(self.enrollment, BASE_TIME)), [self.weak])
        self.assertFalse(selectors.is_review_due(None))

    def test_skill_and_world_summaries_count_unstarted_concepts(self) -> None:
        skill = self.concept.skill
        make_concept(skill)
        make_concept(skill, is_published=False)
        summary = selectors.skill_summary(self.enrollment, skill, now=BASE_TIME)
        self.assertEqual(summary["concepts_total"], 2)
        self.assertEqual(summary["concepts_started"], 1)
        self.assertEqual(summary["weak"], 1)
        self.assertEqual(summary["review_due"], 1)
        self.assertEqual(summary["mastery"], 0.0)

        english = selectors.world_summary(self.english_enrollment, now=BASE_TIME)
        self.assertEqual(english["mastered"], 1)
        self.assertEqual(english["mastery"], 100.0)
        self.assertEqual(english["review_due"], 0)

    def test_selectors_are_query_bounded(self) -> None:
        with self.assertNumQueries(2):
            states = list(selectors.concept_states_for_enrollment(self.enrollment))
            [list(state.mode_states.all()) for state in states]
