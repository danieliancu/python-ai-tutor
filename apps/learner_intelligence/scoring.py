"""Learner intelligence v1: pure, deterministic scoring functions.

Nothing here touches the database. Every function takes attempt-like ``Evidence`` values
(or plain numbers) so the rules can be tested and recalibrated in isolation. Unless stated
otherwise, evidence sequences are ordered newest first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.attempts.models import AttemptStatus
from apps.exercises.models import LearningMode

ALGORITHM_VERSION = 1

MAX_EVIDENCE_ATTEMPTS = 20
RETENTION_HISTORY_LIMIT = 200

# How strongly a success in each learning mode counts as evidence of knowledge.
MODE_WEIGHTS = {
    LearningMode.RECOGNISE: 0.75,
    LearningMode.COMPLETE: 1.00,
    LearningMode.FIX: 1.15,
    LearningMode.CREATE: 1.30,
}
MODE_RANK = {
    LearningMode.RECOGNISE: 1,
    LearningMode.COMPLETE: 2,
    LearningMode.FIX: 3,
    LearningMode.CREATE: 4,
}
# Highest concept mastery allowed by the strongest mode with a correct attempt.
MODE_CEILINGS = {
    LearningMode.RECOGNISE: 65.0,
    LearningMode.COMPLETE: 80.0,
    LearningMode.FIX: 90.0,
    LearningMode.CREATE: 100.0,
}
ADVANCED_MODES = frozenset({LearningMode.FIX, LearningMode.CREATE})
DEFAULT_MODE_WEIGHT = 1.0

RECENCY_DECAY = 0.90

HINT_PENALTY = 0.10
MAX_HINT_PENALTY = 0.50
EXPLANATION_FACTOR = 0.80
SOLUTION_FACTOR = 0.25

RETENTION_GAP_HOURS = 24

TREND_WINDOW = 3
TREND_THRESHOLD = 0.15

# (minimum mastery, base review interval in days), highest threshold first.
REVIEW_BASE_INTERVALS = ((95.0, 30), (85.0, 14), (75.0, 7), (60.0, 3), (40.0, 1), (0.0, 0))
HIGH_RETENTION = 85.0
LOW_RETENTION = 60.0
MAX_REVIEW_DAYS = 60

WEAK_BELOW = 40.0
LEARNING_BELOW = 65.0
MASTERED_FROM = 85.0

JUDGED_STATUSES = frozenset({AttemptStatus.CORRECT, AttemptStatus.INCORRECT})

MASTERY_BAND_NOT_STARTED = "not_started"
MASTERY_BAND_WEAK = "weak"
MASTERY_BAND_LEARNING = "learning"
MASTERY_BAND_PRACTISING = "practising"
MASTERY_BAND_MASTERED = "mastered"

TREND_RISING = "rising"
TREND_STABLE = "stable"
TREND_FALLING = "falling"
TREND_INSUFFICIENT_DATA = "insufficient_data"

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Evidence:
    """The attempt facts intelligence needs; never answers or evaluation specs."""

    status: str
    submitted_at: datetime
    learning_mode: str
    score: float | None = None
    is_correct: bool | None = None
    hint_level: int = 0
    used_explanation: bool = False
    used_solution: bool = False
    duration_seconds: int | None = None
    target_seconds: int | None = None

    @classmethod
    def from_attempt(cls, attempt) -> Evidence:
        exercise = attempt.exercise
        return cls(
            status=attempt.status,
            submitted_at=attempt.submitted_at,
            learning_mode=exercise.learning_mode,
            score=attempt.score,
            is_correct=attempt.is_correct,
            hint_level=attempt.hint_level,
            used_explanation=attempt.used_explanation,
            used_solution=attempt.used_solution,
            duration_seconds=attempt.duration_seconds,
            target_seconds=exercise.target_seconds,
        )


@dataclass(frozen=True)
class ModeMetrics:
    performance: float
    attempt_count: int
    correct_count: int
    independence: float | None
    fluency: float | None
    last_attempt_at: datetime


@dataclass(frozen=True)
class ConceptMetrics:
    mastery: float
    band: str
    retention: float | None
    independence: float | None
    fluency: float | None
    trend: str
    trend_score: float | None
    stability_days: int | None
    review_due_at: datetime | None
    evidence_count: int
    correct_count: int
    retention_evidence_count: int
    last_judged_at: datetime | None
    last_success_at: datetime | None
    modes: dict[str, ModeMetrics] = field(default_factory=dict)


# --- primitives ---------------------------------------------------------------------------


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_score(value: float | None, low: float = 0.0, high: float = 100.0) -> Decimal | None:
    """Clamp and round to two decimals, so floating point noise never reaches storage."""
    if value is None:
        return None
    return Decimal(repr(clamp(float(value), low, high))).quantize(TWO_PLACES, ROUND_HALF_UP)


def is_judged(evidence: Evidence) -> bool:
    return evidence.status in JUDGED_STATUSES


def is_success(evidence: Evidence) -> bool:
    return evidence.status == AttemptStatus.CORRECT


def judged(evidence: Sequence[Evidence]) -> list[Evidence]:
    return [e for e in evidence if is_judged(e)]


def assistance_factor(evidence: Evidence) -> float:
    """1.0 for independent work, lower the more help the learner used."""
    factor = 1.0 - min(MAX_HINT_PENALTY, HINT_PENALTY * max(evidence.hint_level or 0, 0))
    if evidence.used_explanation:
        factor *= EXPLANATION_FACTOR
    if evidence.used_solution:
        factor *= SOLUTION_FACTOR
    return clamp(factor, 0.0, 1.0)


def base_score(evidence: Evidence) -> float:
    """The judged score (0–1), falling back to correctness if the score is missing."""
    if evidence.score is not None:
        return clamp(float(evidence.score), 0.0, 1.0)
    if evidence.is_correct is not None:
        return 1.0 if evidence.is_correct else 0.0
    return 1.0 if is_success(evidence) else 0.0


def attempt_quality(evidence: Evidence) -> float:
    return base_score(evidence) * assistance_factor(evidence)


def mode_weight(learning_mode: str) -> float:
    return MODE_WEIGHTS.get(learning_mode, DEFAULT_MODE_WEIGHT)


def recency_weights(count: int) -> list[float]:
    """Newest first: 1.0, 0.9, 0.81, …"""
    return [RECENCY_DECAY**index for index in range(count)]


def confidence_factor(evidence_count: int) -> float:
    """0.6 for one judged attempt, 0.8 for two, 1.0 from three."""
    if evidence_count <= 0:
        return 0.0
    return min(1.0, 0.4 + 0.2 * evidence_count)


def weighted_average(values: Sequence[float], weights: Sequence[float]) -> float | None:
    total = sum(weights)
    if not values or total <= 0:
        return None
    return sum(v * w for v, w in zip(values, weights, strict=True)) / total


def speed_factor(duration_seconds: int | None, target_seconds: int | None) -> float | None:
    """1.0 within the target time, roughly 0.5 at twice the target; None without timing."""
    if duration_seconds is None or not target_seconds or target_seconds <= 0:
        return None
    return min(1.0, target_seconds / max(duration_seconds, 1))


# --- concept signals ----------------------------------------------------------------------


def recent_judged(evidence: Sequence[Evidence]) -> list[Evidence]:
    return judged(evidence)[:MAX_EVIDENCE_ATTEMPTS]


def strongest_correct_mode(evidence: Sequence[Evidence]) -> str | None:
    modes = [e.learning_mode for e in evidence if is_success(e) and e.learning_mode in MODE_RANK]
    return max(modes, key=MODE_RANK.__getitem__, default=None)


def has_advanced_success(evidence: Sequence[Evidence]) -> bool:
    return any(is_success(e) and e.learning_mode in ADVANCED_MODES for e in evidence)


def calculate_mastery(evidence: Sequence[Evidence]) -> float:
    """0–100 mastery from recent judged evidence, capped by the strongest demonstrated mode."""
    window = recent_judged(evidence)
    if not window:
        return 0.0
    weights = [
        mode_weight(e.learning_mode) * recency
        for e, recency in zip(window, recency_weights(len(window)), strict=True)
    ]
    raw = weighted_average([attempt_quality(e) for e in window], weights) or 0.0
    mastery = raw * 100.0 * confidence_factor(len(window))
    # Without any correct attempt (e.g. only partial credit) the lowest ceiling applies.
    strongest = strongest_correct_mode(window) or LearningMode.RECOGNISE
    ceiling = MODE_CEILINGS[strongest]
    return clamp(min(mastery, ceiling), 0.0, 100.0)


def mastery_band(mastery: float, evidence_count: int, advanced_success: bool) -> str:
    if evidence_count <= 0:
        return MASTERY_BAND_NOT_STARTED
    if mastery < WEAK_BELOW:
        return MASTERY_BAND_WEAK
    if mastery < LEARNING_BELOW:
        return MASTERY_BAND_LEARNING
    if mastery >= MASTERED_FROM and advanced_success:
        return MASTERY_BAND_MASTERED
    return MASTERY_BAND_PRACTISING


def calculate_mode_performance(evidence: Sequence[Evidence]) -> float:
    """0–100 for evidence that already belongs to a single learning mode (no ceiling)."""
    window = recent_judged(evidence)
    if not window:
        return 0.0
    raw = weighted_average([attempt_quality(e) for e in window], recency_weights(len(window)))
    return clamp((raw or 0.0) * 100.0 * confidence_factor(len(window)), 0.0, 100.0)


def calculate_independence(evidence: Sequence[Evidence]) -> float | None:
    """How well the learner succeeds without help; None without judged evidence."""
    window = recent_judged(evidence)
    raw = weighted_average([attempt_quality(e) for e in window], recency_weights(len(window)))
    return None if raw is None else clamp(raw * 100.0, 0.0, 100.0)


def calculate_fluency(evidence: Sequence[Evidence]) -> float | None:
    """Correct, independent and reasonably quick; None without usable timing."""
    values = []
    for e in recent_judged(evidence):
        speed = speed_factor(e.duration_seconds, e.target_seconds)
        if speed is not None:
            values.append(attempt_quality(e) * speed)
    raw = weighted_average(values, recency_weights(len(values)))
    return None if raw is None else clamp(raw * 100.0, 0.0, 100.0)


def retention_checkpoints(evidence: Sequence[Evidence]) -> list[Evidence]:
    """Judged attempts made at least RETENTION_GAP_HOURS after the previous judged attempt.

    Returned newest first. The first judged attempt is never a checkpoint.
    """
    gap = timedelta(hours=RETENTION_GAP_HOURS)
    chronological = sorted(judged(evidence), key=lambda e: e.submitted_at)
    checkpoints = [
        current
        for previous, current in zip(chronological, chronological[1:], strict=False)
        if current.submitted_at - previous.submitted_at >= gap
    ]
    return checkpoints[::-1]


def calculate_retention(evidence: Sequence[Evidence]) -> tuple[float | None, int]:
    """(score, checkpoint count). Spaced recall only: quick repetition proves nothing."""
    checkpoints = retention_checkpoints(evidence)
    window = checkpoints[:MAX_EVIDENCE_ATTEMPTS]
    raw = weighted_average([attempt_quality(e) for e in window], recency_weights(len(window)))
    score = None if raw is None else clamp(raw * 100.0, 0.0, 100.0)
    return score, len(checkpoints)


def calculate_trend(evidence: Sequence[Evidence]) -> tuple[str, float | None]:
    """Compare the latest TREND_WINDOW judged attempts with the TREND_WINDOW before them."""
    window = recent_judged(evidence)
    if len(window) < 2 * TREND_WINDOW:
        return TREND_INSUFFICIENT_DATA, None
    recent = [attempt_quality(e) for e in window[:TREND_WINDOW]]
    previous = [attempt_quality(e) for e in window[TREND_WINDOW : 2 * TREND_WINDOW]]
    delta = clamp(sum(recent) / TREND_WINDOW - sum(previous) / TREND_WINDOW, -1.0, 1.0)
    if delta > TREND_THRESHOLD:
        return TREND_RISING, delta
    if delta < -TREND_THRESHOLD:
        return TREND_FALLING, delta
    return TREND_STABLE, delta


def retention_modifier(retention: float | None) -> float:
    if retention is None:
        return 1.0
    if retention >= HIGH_RETENTION:
        return 1.5
    if retention >= LOW_RETENTION:
        return 1.0
    return 0.5


def base_review_interval(mastery: float) -> int:
    for threshold, days in REVIEW_BASE_INTERVALS:
        if mastery >= threshold:
            return days
    return 0


def calculate_review_interval(mastery: float, retention: float | None) -> int:
    """Whole days until the concept should be reviewed again (0 = due now)."""
    base = base_review_interval(mastery)
    if base == 0:
        return 0
    adjusted = Decimal(repr(base * retention_modifier(retention)))
    days = int(adjusted.quantize(Decimal(1), ROUND_HALF_UP))
    return int(clamp(days, 1, MAX_REVIEW_DAYS))


# --- entry points -------------------------------------------------------------------------


def compute_mode_metrics(evidence: Sequence[Evidence]) -> dict[str, ModeMetrics]:
    """Per-mode metrics for every mode with judged evidence; each uses only its own attempts."""
    by_mode: dict[str, list[Evidence]] = {}
    for e in judged(evidence):
        by_mode.setdefault(e.learning_mode, []).append(e)
    return {
        mode: ModeMetrics(
            performance=calculate_mode_performance(items),
            attempt_count=len(items),
            correct_count=sum(1 for e in items if is_success(e)),
            independence=calculate_independence(items),
            fluency=calculate_fluency(items),
            last_attempt_at=max(e.submitted_at for e in items),
        )
        for mode, items in by_mode.items()
    }


def compute_concept_metrics(evidence: Sequence[Evidence]) -> ConceptMetrics:
    """Every concept-level signal from one learner's evidence for one concept (newest first)."""
    history = sorted(judged(evidence), key=lambda e: e.submitted_at, reverse=True)
    window = history[:MAX_EVIDENCE_ATTEMPTS]
    mastery = calculate_mastery(window)
    retention, retention_count = calculate_retention(history)
    trend, trend_score = calculate_trend(window)
    last_judged_at = history[0].submitted_at if history else None
    successes = [e.submitted_at for e in history if is_success(e)]

    stability_days = review_due_at = None
    if last_judged_at is not None:
        stability_days = calculate_review_interval(mastery, retention)
        review_due_at = last_judged_at + timedelta(days=stability_days)

    return ConceptMetrics(
        mastery=mastery,
        band=mastery_band(mastery, len(window), has_advanced_success(window)),
        retention=retention,
        independence=calculate_independence(window),
        fluency=calculate_fluency(window),
        trend=trend,
        trend_score=trend_score,
        stability_days=stability_days,
        review_due_at=review_due_at,
        evidence_count=len(history),
        correct_count=sum(1 for e in history if is_success(e)),
        retention_evidence_count=retention_count,
        last_judged_at=last_judged_at,
        last_success_at=max(successes, default=None),
        modes=compute_mode_metrics(history),
    )
