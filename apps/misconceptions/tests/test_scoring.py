from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.learner_intelligence.tests.helpers import BASE_TIME
from apps.misconceptions import scoring
from apps.misconceptions.scoring import AttemptEvent, EvidenceRow


def history(pattern: str, exercise_id=None) -> list[AttemptEvent]:
    """Chronological events. S = strong failure, w = weak failure, c = independent correct,
    h = correct with a hint, e = after an explanation, s = after seeing the solution."""
    counters = {"c": 1.0, "h": 0.9, "e": 0.8, "s": 0.25}
    events = []
    for index, char in enumerate(pattern):
        events.append(
            AttemptEvent(
                attempt_id=index + 1,
                exercise_id=exercise_id if exercise_id is not None else 1,
                at=BASE_TIME + timedelta(days=index),
                positive={"S": 1.0, "w": 0.4}.get(char, 0.0),
                counter=counters.get(char, 0.0),
            )
        )
    return events


def summary(pattern: str, **kwargs):
    return scoring.aggregate_misconception(history(pattern, **kwargs))


class GroupingTests(SimpleTestCase):
    def test_one_attempt_counts_once_with_its_strongest_signals(self) -> None:
        rows = [
            EvidenceRow(1, 10, BASE_TIME, "off-by-one", "positive", 0.4),
            EvidenceRow(1, 10, BASE_TIME, "off-by-one", "positive", 1.0),
            EvidenceRow(1, 10, BASE_TIME, "range-step", "positive", 0.4),
            EvidenceRow(2, 10, BASE_TIME + timedelta(hours=1), "off-by-one", "counter", 0.25),
            EvidenceRow(2, 10, BASE_TIME + timedelta(hours=1), "off-by-one", "counter", 0.8),
        ]
        grouped = scoring.group_attempt_evidence(rows)
        self.assertEqual(sorted(grouped), ["off-by-one", "range-step"])
        first, second = grouped["off-by-one"]
        self.assertEqual((first.attempt_id, first.positive, first.counter), (1, 1.0, 0.0))
        self.assertEqual((second.attempt_id, second.positive, second.counter), (2, 0.0, 0.8))
        self.assertTrue(first.is_strong)
        self.assertEqual(scoring.recurrence(grouped["off-by-one"]).positive_events, 1)

    def test_events_are_chronological(self) -> None:
        rows = [
            EvidenceRow(2, 10, BASE_TIME + timedelta(hours=2), "x", "positive", 1.0),
            EvidenceRow(1, 10, BASE_TIME, "x", "positive", 0.4),
        ]
        self.assertEqual([e.attempt_id for e in scoring.group_attempt_evidence(rows)["x"]], [1, 2])


class ConfidenceTests(SimpleTestCase):
    def test_worked_values(self) -> None:
        self.assertAlmostEqual(scoring.calculate_confidence(history("S")), 50.0)
        self.assertAlmostEqual(scoring.calculate_confidence(history("w")), 40 / 1.4, places=4)
        self.assertAlmostEqual(scoring.calculate_confidence(history("SS")), 1.92 / 2.92 * 100)
        self.assertLess(scoring.calculate_confidence(history("www")), 60)
        self.assertGreater(scoring.calculate_confidence(history("wwwww")), 60)
        self.assertEqual(scoring.calculate_confidence([]), 0.0)

    def test_one_event_never_reaches_100(self) -> None:
        self.assertLess(scoring.calculate_confidence(history("S")), 100)
        self.assertLessEqual(scoring.calculate_confidence(history("S" * 100)), 100)

    def test_counter_evidence_lowers_confidence_by_assistance(self) -> None:
        values = [scoring.calculate_confidence(history("SS" + kind)) for kind in "ches"]
        # independent < hint < explanation < solution (least reduction)
        self.assertEqual(values, sorted(values))
        self.assertLess(values[-1], scoring.calculate_confidence(history("SS")))

    def test_recent_evidence_weighs_more(self) -> None:
        self.assertGreater(
            scoring.calculate_confidence(history("ccSS")),
            scoring.calculate_confidence(history("SScc")),
        )

    def test_rounding_and_clamping(self) -> None:
        self.assertEqual(scoring.round_confidence(65.753424), Decimal("65.75"))
        self.assertEqual(scoring.round_confidence(120), Decimal("100.00"))
        self.assertEqual(scoring.round_confidence(-1), Decimal("0.00"))


class StatusTests(SimpleTestCase):
    def test_one_mistake_is_watch(self) -> None:
        for pattern in ("S", "w"):
            with self.subTest(pattern=pattern):
                self.assertEqual(summary(pattern).status, scoring.WATCH)

    def test_repeated_strong_evidence_is_active(self) -> None:
        result = summary("SS")
        self.assertEqual(result.status, scoring.ACTIVE)
        self.assertEqual(result.strong_evidence_count, 2)
        self.assertEqual(result.last_confirmed_at, BASE_TIME + timedelta(days=1))

    def test_weak_candidates_need_more_recurrence(self) -> None:
        self.assertEqual(summary("ww").status, scoring.WATCH)
        self.assertEqual(summary("www").status, scoring.WATCH)  # confidence too low
        self.assertEqual(summary("wwwww").status, scoring.ACTIVE)

    def test_confidence_alone_is_not_enough(self) -> None:
        # A high-confidence but isolated signal cannot be active.
        isolated = scoring.Recurrence(
            distinct_exercises=1, positive_events=1, strong_events=1, counter_events=0
        )
        self.assertFalse(scoring.meets_active_criteria(95.0, isolated))
        distinct = scoring.Recurrence(2, 2, 0, 0)
        self.assertTrue(scoring.meets_active_criteria(60.0, distinct))
        self.assertFalse(scoring.meets_active_criteria(59.99, distinct))
        self.assertTrue(scoring.meets_active_criteria(60.0, scoring.Recurrence(1, 3, 0, 0)))
        self.assertTrue(scoring.meets_active_criteria(60.0, scoring.Recurrence(1, 2, 2, 0)))

    def test_counter_evidence_only_creates_nothing(self) -> None:
        self.assertIsNone(summary("ccc"))
        self.assertIsNone(scoring.aggregate_misconception([]))

    def test_resolution_after_independent_recovery(self) -> None:
        # Two recoveries: no longer active, but confidence (35.7) is not yet below 30.
        self.assertEqual(summary("SScc").status, scoring.WATCH)
        result = summary("SSccc")
        self.assertEqual(result.status, scoring.RESOLVED)
        self.assertEqual(result.resolved_at, BASE_TIME + timedelta(days=4))
        self.assertEqual(result.last_confirmed_at, BASE_TIME + timedelta(days=1))
        self.assertLess(result.confidence, scoring.RESOLVED_THRESHOLD)
        # Further success keeps the original resolution time.
        self.assertEqual(summary("SScccc").resolved_at, BASE_TIME + timedelta(days=4))

    def test_solution_assisted_success_does_not_resolve(self) -> None:
        self.assertNotEqual(summary("SSssssss").status, scoring.RESOLVED)

    def test_never_active_misconceptions_do_not_resolve(self) -> None:
        self.assertEqual(summary("Sccccc").status, scoring.WATCH)

    def test_reactivation(self) -> None:
        self.assertEqual(summary("SSccc").status, scoring.RESOLVED)
        relapse = summary("SScccS")
        self.assertEqual(relapse.status, scoring.WATCH)
        self.assertIsNone(relapse.resolved_at)
        active_again = summary("SScccSSSS")
        self.assertEqual(active_again.status, scoring.ACTIVE)
        self.assertIsNone(active_again.resolved_at)
        self.assertEqual(active_again.last_confirmed_at, BASE_TIME + timedelta(days=8))
        self.assertEqual(active_again.first_seen_at, BASE_TIME)
        self.assertEqual(active_again.last_seen_at, BASE_TIME + timedelta(days=8))

    def test_distinct_exercises_count(self) -> None:
        events = history("SS")
        events[1] = AttemptEvent(2, 99, events[1].at, positive=1.0)
        self.assertEqual(scoring.aggregate_misconception(events).distinct_exercise_count, 2)
        self.assertEqual(summary("SS").distinct_exercise_count, 1)

    def test_window_bounds_old_evidence(self) -> None:
        old_failures_then_success = "S" * 5 + "c" * scoring.CURRENT_EVIDENCE_WINDOW
        self.assertIsNone(summary(old_failures_then_success))
