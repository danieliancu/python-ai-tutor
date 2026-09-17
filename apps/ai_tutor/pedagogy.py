"""The help ladder: Django, not the model, decides how much the tutor may reveal.

guidance → hint → strong hint → explanation → solution. Pure functions only.
"""

from dataclasses import replace

from apps.ai_tutor.constants import MAX_HINT_LEVEL, Intent, ResponseKind
from apps.ai_tutor.types import AssistanceState

ASSISTING_KINDS = frozenset(
    {ResponseKind.HINT, ResponseKind.STRONG_HINT, ResponseKind.EXPLANATION, ResponseKind.SOLUTION}
)


def _next_hint(state: AssistanceState) -> ResponseKind | None:
    if state.hint_level < 1:
        return ResponseKind.HINT
    if state.hint_level < MAX_HINT_LEVEL:
        return ResponseKind.STRONG_HINT
    return None


def grant_response_kind(
    intent: str, state: AssistanceState, *, has_attempt: bool = False
) -> ResponseKind:
    """The exact level the tutor must answer at for this request."""
    if intent == Intent.NEXT_STEP:
        return ResponseKind.NEXT_STEP
    if intent == Intent.ASK:
        return ResponseKind.FEEDBACK if has_attempt else ResponseKind.GUIDANCE
    if intent == Intent.HINT:
        return _next_hint(state) or ResponseKind.STRONG_HINT
    if intent == Intent.EXPLAIN:
        return _next_hint(state) or ResponseKind.EXPLANATION
    if intent == Intent.SOLUTION:
        if (hint := _next_hint(state)) is not None:
            return hint
        if not state.used_explanation:
            return ResponseKind.EXPLANATION
        return ResponseKind.SOLUTION
    raise ValueError(f"Unknown tutor intent: {intent!r}")


def apply_granted(state: AssistanceState, kind: str) -> AssistanceState:
    """The assistance record after a *successful* reply at ``kind``."""
    if kind == ResponseKind.HINT:
        return replace(state, hint_level=max(state.hint_level, 1))
    if kind == ResponseKind.STRONG_HINT:
        return replace(state, hint_level=MAX_HINT_LEVEL)
    if kind == ResponseKind.EXPLANATION:
        return replace(state, used_explanation=True)
    if kind == ResponseKind.SOLUTION:
        return replace(state, used_solution=True)
    return state


def max_disclosure(state: AssistanceState) -> ResponseKind:
    """The most help already unlocked since the latest attempt."""
    if state.used_solution:
        return ResponseKind.SOLUTION
    if state.used_explanation:
        return ResponseKind.EXPLANATION
    if state.hint_level >= MAX_HINT_LEVEL:
        return ResponseKind.STRONG_HINT
    if state.hint_level >= 1:
        return ResponseKind.HINT
    return ResponseKind.GUIDANCE


def solution_allowed(state: AssistanceState, granted: str) -> bool:
    return granted == ResponseKind.SOLUTION or state.used_solution


def disclosure_for(state: AssistanceState, granted: str) -> ResponseKind:
    """The ceiling for this reply: what was already unlocked, or what is granted now."""
    order = [
        ResponseKind.GUIDANCE,
        ResponseKind.HINT,
        ResponseKind.STRONG_HINT,
        ResponseKind.EXPLANATION,
        ResponseKind.SOLUTION,
    ]
    unlocked = max_disclosure(state)
    if granted in order and order.index(granted) > order.index(unlocked):
        return ResponseKind(granted)
    return unlocked


def default_should_retry(kind: str) -> bool:
    return kind in {ResponseKind.HINT, ResponseKind.STRONG_HINT, ResponseKind.EXPLANATION}
