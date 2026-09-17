from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.attempts.models import AttemptStatus
from apps.exercises.models import LearningMode
from apps.learner_intelligence import scoring
from apps.learner_intelligence.tests.helpers import ev, newest_first, series

RECOGNISE = LearningMode.RECOGNISE
COMPLETE = LearningMode.COMPLETE
FIX = LearningMode.FIX
CREATE = LearningMode.CREATE
DAY = 24 * 60


class AssistanceTests(SimpleTestCase):
    def test_help_lowers_the_factor_in_order(self) -> None:
        independent = scoring.assistance_factor(ev())
        hint = scoring.assistance_factor(ev(hint_level=1))
        explanation = scoring.assistance_factor(ev(used_explanation=True))
        solution = scoring.assistance_factor(ev(used_solution=True))
        self.assertEqual(independent, 1.0)
        self.assertAlmostEqual(hint, 0.9)
        self.assertAlmostEqual(explanation, 0.8)
        self.assertAlmostEqual(solution, 0.25)
        self.assertGreater(independent, hint)
        self.assertGreater(hint, explanation)
        self.assertGreater(explanation, solution)

    def test_hint_penalty_is_capped_and_factor_stays_in_range(self) -> None:
        self.assertAlmostEqual(scoring.assistance_factor(ev(hint_level=10)), 0.5)
        everything = ev(hint_level=10, used_explanation=True, used_solution=True)
        self.assertAlmostEqual(scoring.assistance_factor(everything), 0.5 * 0.8 * 0.25)
        self.assertGreaterEqual(scoring.assistance_factor(everything), 0.0)

    def test_quality_uses_score_and_falls_back_to_correctness(self) -> None:
        self.assertEqual(scoring.attempt_quality(ev(True)), 1.0)
        self.assertEqual(scoring.attempt_quality(ev(False)), 0.0)
        self.assertEqual(scoring.attempt_quality(ev(True, score=None)), 1.0)
        self.assertEqual(scoring.attempt_quality(ev(False, score=None)), 0.0)
        self.assertEqual(scoring.attempt_quality(ev(True, score=None, is_correct=None)), 1.0)
        self.assertAlmostEqual(scoring.attempt_quality(ev(True, hint_level=2)), 0.8)

    def test_equivalent_correct_attempts_rank_by_assistance(self) -> None:
        def mastery(**help_used) -> float:
            return scoring.calculate_mastery(series("111", CREATE, **help_used))

        values = [
            mastery(),
            mastery(hint_level=1),
            mastery(used_explanation=True),
            mastery(used_solution=True),
        ]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(len(set(values)), 4)
        self.assertLess(values[-1], 30)
        for value in values:
            self.assertTrue(0 <= value <= 100)


class MasteryTests(SimpleTestCase):
    def test_one_correct_answer_is_not_full_mastery(self) -> None:
        self.assertAlmostEqual(scoring.calculate_mastery([ev(True, CREATE)]), 60.0)
        self.assertAlmostEqual(scoring.calculate_mastery(series("11", CREATE)), 80.0)
        self.assertAlmostEqual(scoring.calculate_mastery(series("111", CREATE)), 100.0)

    def test_no_evidence_is_zero(self) -> None:
        self.assertEqual(scoring.calculate_mastery([]), 0.0)

    def test_recognition_alone_cannot_exceed_65(self) -> None:
        self.assertEqual(scoring.calculate_mastery(series("1" * 15, RECOGNISE)), 65.0)

    def test_mode_ceilings(self) -> None:
        cases = [(COMPLETE, 80.0), (FIX, 90.0), (CREATE, 100.0)]
        for mode, ceiling in cases:
            with self.subTest(mode=mode):
                mixed = newest_first(
                    *series("1" * 10, RECOGNISE),
                    ev(True, mode, minutes=100),
                    ev(True, mode, minutes=101),
                    ev(True, mode, minutes=102),
                )
                value = scoring.calculate_mastery(mixed)
                self.assertGreater(value, 65.0)
                self.assertLessEqual(value, ceiling)
                self.assertEqual(scoring.calculate_mastery(series("11111", mode)), ceiling)

    def test_partial_credit_without_success_uses_the_lowest_ceiling(self) -> None:
        partial = series("xxxxx", CREATE, score=0.9)
        self.assertLessEqual(scoring.calculate_mastery(partial), 65.0)

    def test_incorrect_attempts_reduce_mastery(self) -> None:
        strong = scoring.calculate_mastery(series("11111", CREATE))
        with_mistake = scoring.calculate_mastery(series("1111x", CREATE))
        self.assertLess(with_mistake, strong)
        self.assertAlmostEqual(with_mistake, 3.0951 / 4.0951 * 100, places=3)

    def test_recent_attempts_matter_more(self) -> None:
        improving = scoring.calculate_mastery(series("xx111", CREATE))
        declining = scoring.calculate_mastery(series("111xx", CREATE))
        self.assertGreater(improving, declining)

    def test_only_recent_window_counts(self) -> None:
        old_failures = series("x" * 30 + "1" * scoring.MAX_EVIDENCE_ATTEMPTS, CREATE)
        self.assertEqual(scoring.calculate_mastery(old_failures), 100.0)

    def test_non_judged_statuses_do_not_change_mastery(self) -> None:
        base = series("111x1", FIX)
        for status in (
            AttemptStatus.INVALID,
            AttemptStatus.REVIEW_REQUIRED,
            AttemptStatus.UNSUPPORTED,
            AttemptStatus.UNAVAILABLE,
        ):
            with self.subTest(status=status):
                noisy = newest_first(
                    *base, *(ev(False, FIX, minutes=50 + i, status=status) for i in range(10))
                )
                self.assertEqual(scoring.calculate_mastery(noisy), scoring.calculate_mastery(base))
                self.assertEqual(
                    scoring.compute_concept_metrics(noisy).evidence_count,
                    scoring.compute_concept_metrics(base).evidence_count,
                )


class BandTests(SimpleTestCase):
    def test_band_thresholds(self) -> None:
        cases = [
            (0, 0, False, "not_started"),
            (0, 1, False, "weak"),
            (39.99, 3, False, "weak"),
            (40, 3, False, "learning"),
            (64.99, 3, False, "learning"),
            (65, 3, False, "practising"),
            (84.99, 3, True, "practising"),
            (85, 3, True, "mastered"),
        ]
        for mastery, count, advanced, band in cases:
            with self.subTest(mastery=mastery):
                self.assertEqual(scoring.mastery_band(mastery, count, advanced), band)

    def test_mastered_requires_advanced_success(self) -> None:
        self.assertEqual(scoring.mastery_band(95, 10, False), "practising")
        self.assertEqual(scoring.mastery_band(95, 10, True), "mastered")

    def test_only_recognise_and_complete_success_is_not_mastered(self) -> None:
        evidence = newest_first(*series("1" * 10, RECOGNISE), *series("1" * 10, COMPLETE))
        metrics = scoring.compute_concept_metrics(evidence)
        self.assertEqual(metrics.band, "practising")

    def test_fix_or_create_success_can_be_mastered(self) -> None:
        for mode in (FIX, CREATE):
            with self.subTest(mode=mode):
                metrics = scoring.compute_concept_metrics(series("11111", mode))
                self.assertGreaterEqual(metrics.mastery, 85)
                self.assertEqual(metrics.band, "mastered")

    def test_failed_advanced_attempts_do_not_count_as_advanced(self) -> None:
        evidence = newest_first(*series("11111", COMPLETE), ev(False, FIX, minutes=60))
        self.assertFalse(scoring.has_advanced_success(evidence))


class ModePerformanceTests(SimpleTestCase):
    def test_mode_performance_uses_confidence_without_ceiling(self) -> None:
        self.assertAlmostEqual(scoring.calculate_mode_performance([ev(True, RECOGNISE)]), 60.0)
        self.assertEqual(scoring.calculate_mode_performance(series("111", RECOGNISE)), 100.0)
        self.assertEqual(scoring.calculate_mode_performance([]), 0.0)

    def test_modes_are_scored_separately(self) -> None:
        evidence = newest_first(
            *series("111", RECOGNISE),
            *(ev(False, CREATE, minutes=10 + i) for i in range(3)),
        )
        modes = scoring.compute_mode_metrics(evidence)
        self.assertEqual(set(modes), {RECOGNISE, CREATE})
        self.assertEqual(modes[RECOGNISE].performance, 100.0)
        self.assertEqual(modes[CREATE].performance, 0.0)
        self.assertEqual(modes[CREATE].attempt_count, 3)
        self.assertEqual(modes[CREATE].correct_count, 0)


class IndependenceTests(SimpleTestCase):
    def test_independent_learner_scores_higher_than_assisted_learner(self) -> None:
        learner_a = series("11111")
        learner_b = newest_first(
            ev(minutes=0, hint_level=2),
            ev(minutes=1, used_explanation=True),
            ev(minutes=2, used_solution=True),
            ev(minutes=3, hint_level=1, used_explanation=True),
            ev(minutes=4, used_solution=True),
        )
        a = scoring.calculate_independence(learner_a)
        b = scoring.calculate_independence(learner_b)
        self.assertEqual(a, 100.0)
        self.assertLess(b, 60.0)

    def test_incorrect_unassisted_attempts_are_not_independent(self) -> None:
        self.assertEqual(scoring.calculate_independence(series("xxxxx")), 0.0)

    def test_no_evidence_is_null(self) -> None:
        self.assertIsNone(scoring.calculate_independence([]))
        unsupported = [ev(status=AttemptStatus.UNSUPPORTED)]
        self.assertIsNone(scoring.calculate_independence(unsupported))


class FluencyTests(SimpleTestCase):
    def fluency(self, **fields) -> float | None:
        fields.setdefault("target_seconds", 60)
        return scoring.calculate_fluency([ev(fields.pop("correct", True), **fields)])

    def test_speed_factor(self) -> None:
        self.assertEqual(scoring.speed_factor(30, 60), 1.0)
        self.assertEqual(scoring.speed_factor(120, 60), 0.5)
        self.assertEqual(scoring.speed_factor(0, 60), 1.0)
        self.assertIsNone(scoring.speed_factor(None, 60))
        self.assertIsNone(scoring.speed_factor(30, None))
        self.assertIsNone(scoring.speed_factor(30, 0))

    def test_fluency_cases(self) -> None:
        fast = self.fluency(duration_seconds=30)
        slow = self.fluency(duration_seconds=240)
        fast_with_solution = self.fluency(duration_seconds=30, used_solution=True)
        fast_but_wrong = self.fluency(duration_seconds=10, correct=False)
        self.assertEqual(fast, 100.0)
        self.assertEqual(slow, 25.0)
        self.assertEqual(fast_with_solution, 25.0)
        self.assertEqual(fast_but_wrong, 0.0)

    def test_no_timing_evidence_is_null(self) -> None:
        self.assertIsNone(self.fluency(duration_seconds=None))
        self.assertIsNone(self.fluency(duration_seconds=30, target_seconds=None))
        self.assertIsNone(scoring.calculate_fluency([]))

    def test_untimed_attempts_are_skipped(self) -> None:
        evidence = newest_first(
            ev(False, minutes=1),  # untimed failure: not fluency evidence
            ev(True, minutes=0, duration_seconds=30, target_seconds=60),
        )
        self.assertEqual(scoring.calculate_fluency(evidence), 100.0)


class RetentionTests(SimpleTestCase):
    def test_immediate_repetition_is_not_retention(self) -> None:
        evidence = newest_first(ev(minutes=0), ev(minutes=10))
        self.assertEqual(scoring.retention_checkpoints(evidence), [])
        self.assertEqual(scoring.calculate_retention(evidence), (None, 0))

    def test_first_attempt_is_not_retention(self) -> None:
        self.assertEqual(scoring.calculate_retention([ev(minutes=0)]), (None, 0))

    def test_spaced_attempt_is_retention_evidence(self) -> None:
        later = ev(minutes=2 * DAY)
        evidence = newest_first(ev(minutes=0), ev(minutes=10), later)
        self.assertEqual(scoring.retention_checkpoints(evidence), [later])
        self.assertEqual(scoring.calculate_retention(evidence), (100.0, 1))

    def test_gap_is_measured_from_the_previous_judged_attempt(self) -> None:
        exactly = ev(minutes=DAY)
        just_under = ev(minutes=DAY + DAY - 1)
        evidence = newest_first(ev(minutes=0), exactly, just_under)
        self.assertEqual(scoring.retention_checkpoints(evidence), [exactly])

    def test_non_judged_attempts_do_not_break_the_gap(self) -> None:
        evidence = newest_first(
            ev(minutes=0),
            ev(minutes=DAY + 1, status=AttemptStatus.UNAVAILABLE),
            ev(minutes=DAY + 5),
        )
        self.assertEqual(scoring.calculate_retention(evidence), (100.0, 1))

    def test_correct_spaced_recall_raises_retention(self) -> None:
        before = newest_first(ev(minutes=0), ev(False, minutes=2 * DAY))
        after = newest_first(*before, ev(True, minutes=4 * DAY))
        self.assertEqual(scoring.calculate_retention(before), (0.0, 1))
        score, count = scoring.calculate_retention(after)
        self.assertEqual(count, 2)
        self.assertGreater(score, 0.0)

    def test_incorrect_spaced_recall_lowers_retention(self) -> None:
        before = newest_first(ev(minutes=0), ev(True, minutes=2 * DAY))
        after = newest_first(*before, ev(False, minutes=4 * DAY))
        self.assertEqual(scoring.calculate_retention(before)[0], 100.0)
        self.assertLess(scoring.calculate_retention(after)[0], 100.0)


class TrendTests(SimpleTestCase):
    def test_insufficient_data(self) -> None:
        self.assertEqual(scoring.calculate_trend(series("11111")), ("insufficient_data", None))

    def test_rising(self) -> None:
        self.assertEqual(scoring.calculate_trend(series("xxx111")), ("rising", 1.0))

    def test_falling(self) -> None:
        self.assertEqual(scoring.calculate_trend(series("111xxx")), ("falling", -1.0))

    def test_stable(self) -> None:
        trend, delta = scoring.calculate_trend(series("1x11x1"))
        self.assertEqual(trend, "stable")
        self.assertAlmostEqual(delta, 0.0)

    def test_uses_only_the_latest_six(self) -> None:
        # Older failures fall outside the two comparison windows.
        self.assertEqual(scoring.calculate_trend(series("xxx111111"))[0], "stable")


class ReviewIntervalTests(SimpleTestCase):
    def test_base_interval_boundaries(self) -> None:
        cases = [
            (0, 0),
            (30, 0),
            (39.99, 0),
            (40, 1),
            (50, 1),
            (59.99, 1),
            (60, 3),
            (70, 3),
            (74.99, 3),
            (75, 7),
            (80, 7),
            (84.99, 7),
            (85, 14),
            (90, 14),
            (94.99, 14),
            (95, 30),
            (97, 30),
            (100, 30),
        ]
        for mastery, days in cases:
            with self.subTest(mastery=mastery):
                self.assertEqual(scoring.calculate_review_interval(mastery, None), days)

    def test_high_retention_extends_the_interval(self) -> None:
        self.assertEqual(scoring.calculate_review_interval(97, 90), 45)
        self.assertEqual(scoring.calculate_review_interval(80, 85), 11)
        self.assertEqual(scoring.calculate_review_interval(80, 70), 7)

    def test_poor_retention_shortens_the_interval(self) -> None:
        self.assertEqual(scoring.calculate_review_interval(90, 30), 7)
        self.assertEqual(scoring.calculate_review_interval(50, 10), 1)
        self.assertEqual(scoring.calculate_review_interval(30, 10), 0)

    def test_never_above_sixty_days(self) -> None:
        for mastery in range(0, 101):
            for retention in (None, 0, 59.99, 60, 84.99, 85, 100):
                days = scoring.calculate_review_interval(mastery, retention)
                self.assertTrue(0 <= days <= scoring.MAX_REVIEW_DAYS)

    def test_review_due_at_counts_from_the_last_judged_attempt(self) -> None:
        evidence = series("11111", COMPLETE)
        metrics = scoring.compute_concept_metrics(evidence)
        self.assertEqual(metrics.mastery, 80.0)
        self.assertEqual(metrics.stability_days, 7)
        self.assertEqual(metrics.review_due_at, evidence[0].submitted_at + timedelta(days=7))

    def test_weak_concepts_are_due_immediately(self) -> None:
        metrics = scoring.compute_concept_metrics(series("xxx"))
        self.assertEqual(metrics.stability_days, 0)
        self.assertEqual(metrics.review_due_at, metrics.last_judged_at)

    def test_no_judged_evidence_has_no_review_date(self) -> None:
        metrics = scoring.compute_concept_metrics([ev(status=AttemptStatus.UNSUPPORTED)])
        self.assertIsNone(metrics.review_due_at)
        self.assertIsNone(metrics.stability_days)
        self.assertEqual(metrics.band, "not_started")


class RoundingTests(SimpleTestCase):
    def test_round_score_removes_float_noise_and_clamps(self) -> None:
        self.assertEqual(scoring.round_score(79.9999999993), Decimal("80.00"))
        self.assertEqual(scoring.round_score(12.345), Decimal("12.35"))
        self.assertEqual(scoring.round_score(101), Decimal("100.00"))
        self.assertEqual(scoring.round_score(-3), Decimal("0.00"))
        self.assertEqual(scoring.round_score(1.7, -1, 1), Decimal("1.00"))
        self.assertIsNone(scoring.round_score(None))

    def test_confidence_factor(self) -> None:
        self.assertEqual(scoring.confidence_factor(0), 0.0)
        self.assertAlmostEqual(scoring.confidence_factor(1), 0.6)
        self.assertAlmostEqual(scoring.confidence_factor(2), 0.8)
        self.assertEqual(scoring.confidence_factor(3), 1.0)
        self.assertEqual(scoring.confidence_factor(50), 1.0)
