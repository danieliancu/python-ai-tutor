from django.test import TestCase

from apps.attempts.selectors import (
    attempt_history_for_exercise,
    attempts_for_learner,
    latest_attempt_for_exercise,
    mistake_counts_for_enrollment,
    recent_attempts_for_enrollment,
)
from apps.attempts.tests.helpers import SECRET_OPTION, AttemptFixtures


class SelectorTests(AttemptFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.a1 = self.record(self.mcq, "opt-a")
        self.a2 = self.record(self.mcq, "opt-z")
        self.a3 = self.record(self.mcq, SECRET_OPTION)
        self.g1 = self.record(self.gap, "wrong")
        self.g2 = self.record(self.gap, "also wrong")
        self.n1 = self.record(self.numeric, "1")

    def test_history_for_exercise_is_newest_first(self) -> None:
        history = list(attempt_history_for_exercise(self.enrollment, self.mcq))
        self.assertEqual(history, [self.a3, self.a2, self.a1])
        self.assertEqual([a.attempt_number for a in history], [3, 2, 1])
        self.assertEqual(list(attempt_history_for_exercise(self.maths_enrollment, self.mcq)), [])

    def test_latest_attempt(self) -> None:
        self.assertEqual(latest_attempt_for_exercise(self.enrollment, self.mcq), self.a3)
        self.assertEqual(latest_attempt_for_exercise(self.enrollment, self.gap), self.g2)
        self.assertIsNone(latest_attempt_for_exercise(self.enrollment, self.code))

    def test_recent_attempts_are_per_enrollment_and_limited(self) -> None:
        self.assertEqual(
            recent_attempts_for_enrollment(self.enrollment),
            [self.g2, self.g1, self.a3, self.a2, self.a1],
        )
        self.assertEqual(
            recent_attempts_for_enrollment(self.enrollment, limit=2), [self.g2, self.g1]
        )
        self.assertEqual(recent_attempts_for_enrollment(self.maths_enrollment), [self.n1])

    def test_mistake_counts(self) -> None:
        self.assertEqual(
            mistake_counts_for_enrollment(self.enrollment),
            {"wrong_option": 1, "invalid_option": 1, "incorrect_value": 2},
        )
        self.assertEqual(
            mistake_counts_for_enrollment(self.maths_enrollment), {"incorrect_value": 1}
        )
        self.assertEqual(mistake_counts_for_enrollment(self.english_enrollment), {})
        with self.assertNumQueries(1):
            mistake_counts_for_enrollment(self.enrollment)

    def test_learner_queryset_prefetches_mistakes(self) -> None:
        with self.assertNumQueries(2):
            attempts = list(attempts_for_learner(self.user))
            codes = [m.code for attempt in attempts for m in attempt.mistakes.all()]
        self.assertEqual(len(attempts), 6)
        self.assertEqual(len(codes), 5)
