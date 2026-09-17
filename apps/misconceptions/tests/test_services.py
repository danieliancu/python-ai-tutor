from decimal import Decimal

from django.forms.models import model_to_dict
from django.test import TestCase

from apps.accounts.tests.helpers import make_user
from apps.attempts.models import AttemptMistake, AttemptStatus, ExerciseAttempt
from apps.learners.models import Enrollment, LearnerProfile
from apps.misconceptions import selectors
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.scoring import MISCONCEPTION_ALGORITHM_VERSION
from apps.misconceptions.services import refresh_for_attempt
from apps.misconceptions.tests.helpers import COMPARISON_REFERENCE, MisconceptionFixtures

DAY = 24 * 60


def snapshot(enrollment) -> dict:
    evidence = [
        model_to_dict(row, exclude=["id"]) | {"created_at": row.created_at}
        for row in MisconceptionEvidence.objects.filter(attempt__enrollment=enrollment).order_by(
            "attempt_id", "code", "kind", "source"
        )
    ]
    states = [
        model_to_dict(row, exclude=["id"]) | {"updated_at": row.updated_at}
        for row in MisconceptionState.objects.filter(enrollment=enrollment).order_by("code")
    ]
    return {"evidence": evidence, "states": states}


class RefreshTests(MisconceptionFixtures, TestCase):
    def test_one_mistake_is_only_watched(self) -> None:
        self.wrong(self.tagged)
        states = self.refresh()
        self.assertEqual([(s.code, s.status) for s in states], [("off-by-one", "watch")])
        state = self.state("off-by-one")
        self.assertEqual(state.confidence_score, Decimal("28.57"))
        self.assertEqual(
            (
                state.positive_evidence_count,
                state.strong_evidence_count,
                state.distinct_exercise_count,
            ),
            (1, 0, 1),
        )
        self.assertEqual(state.algorithm_version, MISCONCEPTION_ALGORITHM_VERSION)
        self.assertIsNone(state.last_confirmed_at)

    def test_one_strong_mistake_is_still_watched(self) -> None:
        self.wrong(self.range_gap, submitted_answer="5")
        self.refresh()
        state = self.state("range-exclusive-stop")
        self.assertEqual((state.status, state.strong_evidence_count), ("watch", 1))
        self.assertEqual(state.confidence_score, Decimal("50.00"))

    def test_ambiguous_tags_never_become_active_from_one_failure(self) -> None:
        self.wrong(self.ambiguous)
        states = self.refresh()
        self.assertEqual(
            sorted((s.code, s.status) for s in states),
            [("alpha-idea", "watch"), ("beta-idea", "watch"), ("gamma-idea", "watch")],
        )

    def test_repeated_strong_failures_become_active(self) -> None:
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.range_gap, 10, submitted_answer="5")
        self.refresh()
        state = self.state("range-exclusive-stop")
        self.assertEqual(state.status, "active")
        self.assertEqual(state.confidence_score, Decimal("65.75"))
        self.assertEqual(state.last_confirmed_at, self.at(10))
        self.assertEqual((state.first_seen_at, state.last_seen_at), (self.at(0), self.at(10)))

    def test_weak_failures_on_distinct_exercises_or_repeated(self) -> None:
        for minutes in range(5):
            self.wrong(self.tagged if minutes % 2 else self.tagged_again, minutes)
        self.refresh()
        state = self.state("off-by-one")
        self.assertEqual(state.status, "active")
        self.assertEqual((state.distinct_exercise_count, state.positive_evidence_count), (2, 5))

    def test_specific_and_generic_signals_count_as_one_event(self) -> None:
        attempt = self.wrong(self.range_gap, submitted_answer="5")
        self.refresh()
        sources = set(
            self.evidence(attempt=attempt, code="off-by-one").values_list("source", "strength")
        )
        self.assertEqual(
            sources,
            {("exercise_tag", Decimal("0.40")), ("python_fill_gap_off_by_one", Decimal("1.00"))},
        )
        state = self.state("off-by-one")
        self.assertEqual((state.positive_evidence_count, state.strong_evidence_count), (1, 1))
        self.assertEqual(state.confidence_score, Decimal("50.00"))

    def test_counter_evidence_depends_on_assistance(self) -> None:
        confidences = {}
        for label, help_used in (
            ("independent", {}),
            ("hint", {"hint_level": 1}),
            ("explanation", {"used_explanation": True}),
            ("solution", {"used_solution": True}),
        ):
            ExerciseAttempt.objects.all().delete()
            self.wrong(self.range_gap, 0, submitted_answer="5")
            self.wrong(self.range_gap, 1, submitted_answer="5")
            self.right(self.range_gap, 2, **help_used)
            self.refresh()
            confidences[label] = self.state("off-by-one").confidence_score
        self.assertLess(confidences["independent"], confidences["hint"])
        self.assertLess(confidences["hint"], confidences["explanation"])
        self.assertLess(confidences["explanation"], confidences["solution"])
        self.assertLess(confidences["solution"], Decimal("65.75"))

    def test_resolution_and_reactivation(self) -> None:
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.range_gap, DAY, submitted_answer="5")
        self.refresh()
        self.assertEqual(self.state("off-by-one").status, "active")

        for day in (2, 3, 4):
            self.right(self.range_gap, day * DAY)
        self.refresh()
        state = self.state("off-by-one")
        self.assertEqual(state.status, "resolved")
        self.assertEqual(state.resolved_at, self.at(4 * DAY))
        self.assertLess(state.confidence_score, Decimal("30"))
        self.assertEqual(state.last_confirmed_at, self.at(DAY))

        for day in (5, 6, 7, 8):
            self.wrong(self.range_gap, day * DAY, submitted_answer="5")
        self.refresh()
        state = self.state("off-by-one")
        self.assertEqual(state.status, "active")
        self.assertIsNone(state.resolved_at)
        self.assertEqual(state.last_confirmed_at, self.at(8 * DAY))

    def test_unjudged_statuses_create_no_evidence(self) -> None:
        for minutes, status in enumerate(
            [
                AttemptStatus.UNSUPPORTED,
                AttemptStatus.UNAVAILABLE,
                AttemptStatus.REVIEW_REQUIRED,
                AttemptStatus.INVALID,
            ]
        ):
            self.make_attempt(self.tagged, status, at=self.at(minutes))
        self.assertEqual(self.refresh(), [])
        self.assertFalse(MisconceptionEvidence.objects.exists())

    def test_raw_mistakes_are_not_misconceptions(self) -> None:
        untagged = self.mcq  # AttemptFixtures' exercise has no misconception tags
        attempt = self.make_attempt(
            untagged, "incorrect", at=self.at(0), diagnostics={"reason": "output_mismatch"}
        )
        AttemptMistake.objects.create(attempt=attempt, code="output_mismatch")
        self.wrong(self.tagged, 1)
        self.refresh()
        codes = set(MisconceptionState.objects.values_list("code", flat=True))
        self.assertEqual(codes, {"off-by-one"})
        self.assertFalse(self.evidence(code="output_mismatch").exists())

    def test_counter_evidence_alone_creates_no_state(self) -> None:
        self.right(self.tagged)
        self.assertEqual(self.refresh(), [])
        self.assertEqual(self.evidence(kind="counter").count(), 1)

    def test_refresh_is_idempotent(self) -> None:
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.comparison, 1, submitted_answer=COMPARISON_REFERENCE.replace(">", "<"))
        self.right(self.tagged, 2, hint_level=2)
        self.wrong(self.ambiguous, 3)
        self.refresh()
        first = snapshot(self.enrollment)
        self.refresh()
        self.assertEqual(snapshot(self.enrollment), first)
        self.assertEqual(len(first["evidence"]), 11)  # 4 + 3 + 1 + 3
        self.assertEqual(
            MisconceptionEvidence.objects.count(),
            MisconceptionEvidence.objects.values("attempt", "code", "kind", "source")
            .distinct()
            .count(),
        )

    def test_stale_derived_rows_are_removed(self) -> None:
        attempt = self.wrong(self.tagged)
        self.refresh()
        self.assertTrue(MisconceptionState.objects.exists())
        # The exercise loses its tag: evidence and state disappear on the next refresh.
        self.tagged.evaluation_spec = {"correct_option": "a"}
        self.tagged.save()
        self.assertEqual(self.refresh(), [])
        self.assertFalse(self.evidence(attempt=attempt).exists())
        self.assertFalse(MisconceptionState.objects.exists())

    def test_refresh_for_attempt(self) -> None:
        attempt = self.wrong(self.tagged)
        states = refresh_for_attempt(attempt)
        self.assertEqual(
            [(s.enrollment, s.concept) for s in states], [(self.enrollment, self.concept)]
        )

    def test_learners_are_independent(self) -> None:
        other = make_user("other")
        other_enrollment = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=other), world=self.python_world
        )
        for minutes in (0, 1):
            self.wrong(self.range_gap, minutes, submitted_answer="5")
            self.make_attempt(
                self.range_gap, "correct", enrollment=other_enrollment, at=self.at(minutes)
            )
        self.refresh()
        self.refresh(other_enrollment)
        self.assertEqual(self.state("off-by-one").status, "active")
        self.assertFalse(MisconceptionState.objects.filter(enrollment=other_enrollment).exists())
        self.assertEqual(
            self.evidence(attempt__enrollment=other_enrollment, kind="counter").count(), 4
        )

    def test_enrollments_are_independent(self) -> None:
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.range_gap, 1, submitted_answer="5")
        self.refresh()
        for enrollment, concept in (
            (self.english_enrollment, self.english_concept),
            (self.maths_enrollment, self.maths_concept),
        ):
            self.assertEqual(self.refresh(enrollment, concept), [])
        self.assertEqual(
            set(MisconceptionState.objects.values_list("enrollment_id", flat=True)),
            {self.enrollment.pk},
        )


class SelectorTests(MisconceptionFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.range_gap, 1, submitted_answer="5")
        self.wrong(self.ambiguous, 2)
        self.refresh()

    def test_status_selectors(self) -> None:
        active = [s.code for s in selectors.active_misconceptions(self.enrollment)]
        self.assertEqual(active, ["off-by-one", "range-exclusive-stop"])
        watch = [s.code for s in selectors.watch_misconceptions(self.enrollment)]
        self.assertEqual(watch, ["alpha-idea", "beta-idea", "gamma-idea"])
        self.assertFalse(selectors.resolved_misconceptions(self.enrollment).exists())
        self.assertEqual(
            len(selectors.misconceptions_for_concept(self.enrollment, self.concept)), 5
        )
        self.assertEqual(len(selectors.top_active_misconceptions(self.enrollment, limit=1)), 1)
        self.assertEqual(selectors.misconceptions_for_world(self.enrollment).count(), 5)
        self.assertFalse(selectors.active_misconceptions(self.english_enrollment).exists())

    def test_world_selector_skips_unpublished_concepts(self) -> None:
        self.concept.is_published = False
        self.concept.save()
        self.assertFalse(selectors.misconceptions_for_world(self.enrollment).exists())
