"""Which concept deserves attention, and why. Pure functions over ``ConceptContext``."""

from collections.abc import Iterable
from datetime import datetime

from apps.next_action import constants as c
from apps.next_action.types import ActionCandidate, ConceptContext

MASTERED = "mastered"
FALLING = "falling"


def concept_started(has_state: bool, has_attempts: bool) -> bool:
    """Attempts count even when derived state is (temporarily) missing."""
    return has_state or has_attempts


def _bounded(value: float, limit: float) -> float:
    return max(0.0, min(limit, value))


def mastery_gap(context: ConceptContext) -> float:
    return _bounded((100.0 - context.mastery) * c.GAP_WEIGHT, c.MAX_GAP_COMPONENT)


def _shared_bonuses(context: ConceptContext, *, watch: bool = True) -> float:
    bonus = c.FALLING_TREND_BONUS if context.trend == FALLING else 0.0
    if watch and context.watch_codes:
        bonus += c.WATCH_BONUS
    if context.is_most_recent:
        bonus += c.CONTINUITY_BONUS
    return bonus


def is_review_due(context: ConceptContext, now: datetime) -> bool:
    return context.review_due_at is not None and context.review_due_at <= now


def remediation_urgency(context: ConceptContext) -> float:
    top = context.active_misconceptions[0].confidence if context.active_misconceptions else 0.0
    return _bounded(top, 100.0) + mastery_gap(context) + _shared_bonuses(context, watch=False)


def review_urgency(context: ConceptContext, now: datetime) -> float:
    overdue_days = (now - context.review_due_at).total_seconds() / 86_400
    if context.retention is None:
        retention_gap = c.UNKNOWN_RETENTION_COMPONENT
    else:
        retention_gap = _bounded((100.0 - context.retention) * c.GAP_WEIGHT, c.MAX_GAP_COMPONENT)
    return (
        _bounded(overdue_days, c.MAX_OVERDUE_DAYS)
        + retention_gap
        + mastery_gap(context)
        + _shared_bonuses(context, watch=False)
    )


def practice_urgency(context: ConceptContext) -> float:
    gap = max(0.0, c.PROGRESSION_THRESHOLD - context.mastery) * c.STRENGTHEN_GAP_WEIGHT
    return gap + _shared_bonuses(context)


def missing_modes(context: ConceptContext) -> list[str]:
    return [mode for mode in c.MODE_ORDER if mode in context.available_modes - context.mode_success]


def deepen_reasons(context: ConceptContext) -> list[str]:
    reasons = []
    if context.band != MASTERED:
        reasons.append(c.NOT_YET_MASTERED)
    if missing_modes(context):
        reasons.append(c.ADVANCED_MODE_GAP)
    if any(
        context.mode_performance.get(mode, 0.0) < c.MODE_WEAKNESS_THRESHOLD
        for mode in context.mode_success & context.available_modes
    ):
        reasons.append(c.MODE_WEAKNESS)
    if context.trend == FALLING:
        reasons.append(c.FALLING_TREND)
    if context.watch_codes:
        reasons.append(c.WATCH_MISCONCEPTION)
    return reasons


def deepen_urgency(context: ConceptContext) -> float:
    return (
        mastery_gap(context)
        + c.MISSING_MODE_WEIGHT * len(missing_modes(context))
        + _shared_bonuses(context)
    )


def _modifiers(context: ConceptContext, *, watch: bool = True) -> tuple[str, ...]:
    extra = []
    if context.trend == FALLING:
        extra.append(c.FALLING_TREND)
    if watch and context.watch_codes:
        extra.append(c.WATCH_MISCONCEPTION)
    return tuple(extra)


def _review_modifiers(context: ConceptContext) -> tuple[str, ...]:
    # Weak concepts are due immediately (Phase 6 scheduling); say so explicitly.
    weak = (c.BELOW_PROGRESSION_THRESHOLD,) if context.mastery < c.PROGRESSION_THRESHOLD else ()
    return (*weak, *_modifiers(context))


def candidate_for(context: ConceptContext, now: datetime) -> ActionCandidate | None:
    """The single highest-tier action this concept qualifies for, if any."""

    def make(action, tier, urgency, reasons, codes=()):
        return ActionCandidate(
            action_type=action,
            concept_id=context.concept_id,
            priority_tier=tier,
            urgency_score=urgency,
            reason_codes=tuple(dict.fromkeys(reasons)),
            skill_order=context.skill_order,
            concept_order=context.concept_order,
            misconception_codes=tuple(codes),
        )

    if context.active_misconceptions:
        return make(
            c.REMEDIATE,
            c.REMEDIATE_TIER,
            remediation_urgency(context),
            (c.ACTIVE_MISCONCEPTION, *_modifiers(context, watch=False)),
            (m.code for m in context.active_misconceptions),
        )
    if context.started and is_review_due(context, now):
        return make(
            c.REVIEW,
            c.REVIEW_TIER,
            review_urgency(context, now),
            (c.REVIEW_DUE, *_review_modifiers(context)),
            context.watch_codes,
        )
    if context.started and context.mastery < c.PROGRESSION_THRESHOLD:
        return make(
            c.PRACTICE,
            c.STRENGTHEN_TIER,
            practice_urgency(context),
            (c.BELOW_PROGRESSION_THRESHOLD, *_modifiers(context)),
            context.watch_codes,
        )
    if not context.started:
        if context.has_exercises and context.prerequisites_ready:
            return make(c.LEARN, c.INTRODUCE_TIER, 0.0, (c.NEW_CONCEPT_READY,))
        return None
    reasons = deepen_reasons(context)
    if reasons:
        return make(
            c.PRACTICE, c.DEEPEN_TIER, deepen_urgency(context), reasons, context.watch_codes
        )
    return None


def rank_candidates(candidates: Iterable[ActionCandidate]) -> list[ActionCandidate]:
    """Tier first, then urgency, then authored curriculum order (fully deterministic)."""
    return sorted(candidates, key=lambda candidate: candidate.rank_key)


def is_course_complete(contexts: Iterable[ConceptContext], now: datetime) -> bool:
    """Every published concept mastered, nothing to remediate, no review due.

    WATCH misconceptions and optional deepening never block completion.
    """
    contexts = list(contexts)
    return bool(contexts) and all(
        ctx.band == MASTERED and not ctx.active_misconceptions and not is_review_due(ctx, now)
        for ctx in contexts
    )
