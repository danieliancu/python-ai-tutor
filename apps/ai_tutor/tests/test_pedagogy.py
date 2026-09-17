from django.test import SimpleTestCase

from apps.ai_tutor.constants import Intent, ResponseKind
from apps.ai_tutor.pedagogy import (
    apply_granted,
    default_should_retry,
    disclosure_for,
    grant_response_kind,
    max_disclosure,
    solution_allowed,
)
from apps.ai_tutor.types import AssistanceState

FRESH = AssistanceState()


def ladder(intent: str, steps: int, state: AssistanceState = FRESH):
    kinds = []
    for _ in range(steps):
        kind = grant_response_kind(intent, state)
        kinds.append(kind)
        state = apply_granted(state, kind)
    return kinds, state


class HelpLadderTests(SimpleTestCase):
    def test_hint_requests(self) -> None:
        kinds, state = ladder(Intent.HINT, 4)
        self.assertEqual(
            kinds,
            [
                ResponseKind.HINT,
                ResponseKind.STRONG_HINT,
                ResponseKind.STRONG_HINT,
                ResponseKind.STRONG_HINT,
            ],
        )
        self.assertEqual(state, AssistanceState(hint_level=2))

    def test_solution_requests_escalate_progressively(self) -> None:
        kinds, state = ladder(Intent.SOLUTION, 5)
        self.assertEqual(
            kinds,
            [
                ResponseKind.HINT,
                ResponseKind.STRONG_HINT,
                ResponseKind.EXPLANATION,
                ResponseKind.SOLUTION,
                ResponseKind.SOLUTION,
            ],
        )
        self.assertEqual(state, AssistanceState(2, True, True))

    def test_explain_requests_respect_hints_first(self) -> None:
        kinds, state = ladder(Intent.EXPLAIN, 4)
        self.assertEqual(
            kinds,
            [
                ResponseKind.HINT,
                ResponseKind.STRONG_HINT,
                ResponseKind.EXPLANATION,
                ResponseKind.EXPLANATION,
            ],
        )
        self.assertEqual(state, AssistanceState(2, True, False))

    def test_ask_and_next_step_never_escalate(self) -> None:
        for intent in (Intent.ASK, Intent.NEXT_STEP):
            with self.subTest(intent=intent):
                _, state = ladder(intent, 5)
                self.assertEqual(state, FRESH)
        self.assertEqual(grant_response_kind(Intent.ASK, FRESH), ResponseKind.GUIDANCE)
        self.assertEqual(
            grant_response_kind(Intent.ASK, FRESH, has_attempt=True), ResponseKind.FEEDBACK
        )
        self.assertEqual(grant_response_kind(Intent.NEXT_STEP, FRESH), ResponseKind.NEXT_STEP)

    def test_unknown_intent(self) -> None:
        with self.assertRaises(ValueError):
            grant_response_kind("solve_it_all", FRESH)

    def test_disclosure_ceiling(self) -> None:
        self.assertEqual(max_disclosure(FRESH), ResponseKind.GUIDANCE)
        self.assertEqual(max_disclosure(AssistanceState(1)), ResponseKind.HINT)
        self.assertEqual(max_disclosure(AssistanceState(2)), ResponseKind.STRONG_HINT)
        self.assertEqual(max_disclosure(AssistanceState(2, True)), ResponseKind.EXPLANATION)
        self.assertEqual(max_disclosure(AssistanceState(2, True, True)), ResponseKind.SOLUTION)
        self.assertEqual(disclosure_for(FRESH, ResponseKind.HINT), ResponseKind.HINT)
        self.assertEqual(
            disclosure_for(AssistanceState(2, True), ResponseKind.GUIDANCE),
            ResponseKind.EXPLANATION,
        )

    def test_solution_is_only_allowed_once_unlocked(self) -> None:
        self.assertFalse(solution_allowed(FRESH, ResponseKind.GUIDANCE))
        self.assertFalse(solution_allowed(AssistanceState(2, True), ResponseKind.GUIDANCE))
        self.assertTrue(solution_allowed(AssistanceState(2, True), ResponseKind.SOLUTION))
        self.assertTrue(solution_allowed(AssistanceState(2, True, True), ResponseKind.GUIDANCE))

    def test_should_retry_defaults(self) -> None:
        self.assertTrue(default_should_retry(ResponseKind.HINT))
        self.assertFalse(default_should_retry(ResponseKind.SOLUTION))
        self.assertFalse(default_should_retry(ResponseKind.NEXT_STEP))
