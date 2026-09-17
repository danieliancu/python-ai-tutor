"""Misconception engine v1: pure, deterministic aggregation.

``confidence`` (0–100) is a deterministic evidence-strength score for product logic. It is
not a probability in any statistical sense.

A misconception needs *recurring* evidence to become ACTIVE: one wrong answer only puts it on
WATCH. Correct work counts against it, and enough later independent success RESOLVES it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

MISCONCEPTION_ALGORITHM_VERSION = 1

CANDIDATE_STRENGTH = 0.40  # an exercise tag on a failed attempt: "may be involved"
STRONG_STRENGTH = 1.00  # a specific deterministic detector hit
STRONG_MIN = 0.80  # positive strength that counts as strong evidence
MEANINGFUL_COUNTER_MIN = 0.50  # counter strength that counts towards recovery

EVIDENCE_RECENCY_DECAY = 0.92
PRIOR_WEIGHT = 1.0
ACTIVE_THRESHOLD = 60.0
RESOLVED_THRESHOLD = 30.0

MIN_DISTINCT_EXERCISES = 2
MIN_POSITIVE_EVENTS = 3
MIN_STRONG_EVENTS = 2
MIN_RECOVERY_COUNTERS = 2

MISCONCEPTION_HISTORY_LIMIT = 200
CURRENT_EVIDENCE_WINDOW = 40

WATCH = "watch"
ACTIVE = "active"
RESOLVED = "resolved"

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class EvidenceRow:
    """One stored evidence signal with the attempt facts aggregation needs."""

    attempt_id: int
    exercise_id: int
    at: datetime
    code: str
    kind: str
    strength: float


@dataclass(frozen=True)
class AttemptEvent:
    """All evidence one attempt gives for one code, reduced to its strongest signals."""

    attempt_id: int
    exercise_id: int
    at: datetime
    positive: float = 0.0
    counter: float = 0.0

    @property
    def is_positive(self) -> bool:
        return self.positive > 0

    @property
    def is_strong(self) -> bool:
        return self.positive >= STRONG_MIN

    @property
    def is_meaningful_counter(self) -> bool:
        return self.counter >= MEANINGFUL_COUNTER_MIN


@dataclass(frozen=True)
class Recurrence:
    distinct_exercises: int
    positive_events: int
    strong_events: int
    counter_events: int


@dataclass(frozen=True)
class MisconceptionSummary:
    status: str
    confidence: float
    positive_evidence_count: int
    counter_evidence_count: int
    strong_evidence_count: int
    distinct_exercise_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    last_confirmed_at: datetime | None
    resolved_at: datetime | None


def round_confidence(value: float) -> Decimal:
    clamped = max(0.0, min(100.0, float(value)))
    return Decimal(repr(clamped)).quantize(TWO_PLACES, ROUND_HALF_UP)


def group_attempt_evidence(rows: Iterable[EvidenceRow]) -> dict[str, list[AttemptEvent]]:
    """Per code, one event per attempt (strongest positive and counter), oldest first.

    A generic candidate and a specific detector firing on the same submission are one event,
    so a single answer is never counted twice.
    """
    merged: dict[tuple[str, int], dict] = {}
    for row in rows:
        event = merged.setdefault(
            (row.code, row.attempt_id),
            {
                "attempt_id": row.attempt_id,
                "exercise_id": row.exercise_id,
                "at": row.at,
                "positive": 0.0,
                "counter": 0.0,
            },
        )
        key = "positive" if row.kind == "positive" else "counter"
        event[key] = max(event[key], float(row.strength))

    grouped: dict[str, list[AttemptEvent]] = {}
    for (code, _), values in merged.items():
        grouped.setdefault(code, []).append(AttemptEvent(**values))
    for events in grouped.values():
        events.sort(key=lambda e: (e.at, e.attempt_id))
    return grouped


def calculate_confidence(events: Sequence[AttemptEvent]) -> float:
    """``events`` oldest first; only the latest CURRENT_EVIDENCE_WINDOW count."""
    window = list(events)[-CURRENT_EVIDENCE_WINDOW:][::-1]
    positive = sum(e.positive * EVIDENCE_RECENCY_DECAY**i for i, e in enumerate(window))
    counter = sum(e.counter * EVIDENCE_RECENCY_DECAY**i for i, e in enumerate(window))
    confidence = positive / (positive + counter + PRIOR_WEIGHT) * 100.0
    return max(0.0, min(100.0, confidence))


def recurrence(events: Sequence[AttemptEvent]) -> Recurrence:
    window = list(events)[-CURRENT_EVIDENCE_WINDOW:]
    positives = [e for e in window if e.is_positive]
    return Recurrence(
        distinct_exercises=len({e.exercise_id for e in positives}),
        positive_events=len(positives),
        strong_events=sum(1 for e in positives if e.is_strong),
        counter_events=sum(1 for e in window if e.counter > 0),
    )


def meets_active_criteria(confidence: float, seen: Recurrence) -> bool:
    return confidence >= ACTIVE_THRESHOLD and (
        seen.distinct_exercises >= MIN_DISTINCT_EXERCISES
        or seen.positive_events >= MIN_POSITIVE_EVENTS
        or seen.strong_events >= MIN_STRONG_EVENTS
    )


def recovery_counters(events: Sequence[AttemptEvent]) -> list[AttemptEvent]:
    """Meaningful correct work after the most recent positive evidence (oldest first)."""
    recovered: list[AttemptEvent] = []
    for event in events:
        if event.is_positive:
            recovered = []
        elif event.is_meaningful_counter:
            recovered.append(event)
    return recovered


def calculate_status(
    confidence: float, seen: Recurrence, events: Sequence[AttemptEvent], ever_active: bool
) -> str:
    if meets_active_criteria(confidence, seen):
        return ACTIVE
    if (
        ever_active
        and confidence < RESOLVED_THRESHOLD
        and len(recovery_counters(events)) >= MIN_RECOVERY_COUNTERS
    ):
        return RESOLVED
    return WATCH


def aggregate_misconception(events: Sequence[AttemptEvent]) -> MisconceptionSummary | None:
    """Replay a code's events (oldest first) to find its current status and history.

    Returns None when the current window holds no positive evidence: counter-evidence alone
    never creates a misconception.
    """
    history = sorted(events, key=lambda e: (e.at, e.attempt_id))
    window = history[-CURRENT_EVIDENCE_WINDOW:]
    if not any(e.is_positive for e in window):
        return None

    status = WATCH
    ever_active = False
    last_confirmed_at = resolved_at = None
    confidence = 0.0
    for index, event in enumerate(history):
        seen_so_far = history[: index + 1]
        confidence = calculate_confidence(seen_so_far)
        seen = recurrence(seen_so_far)
        status = calculate_status(confidence, seen, seen_so_far, ever_active)
        if status == ACTIVE:
            ever_active = True
            last_confirmed_at = event.at
            resolved_at = None
        elif status == RESOLVED:
            # The counter-evidence event that first satisfied resolution.
            resolved_at = resolved_at or event.at
        else:
            resolved_at = None

    seen = recurrence(history)
    positives = [e for e in window if e.is_positive]
    return MisconceptionSummary(
        status=status,
        confidence=confidence,
        positive_evidence_count=seen.positive_events,
        counter_evidence_count=seen.counter_events,
        strong_evidence_count=seen.strong_events,
        distinct_exercise_count=seen.distinct_exercises,
        first_seen_at=positives[0].at,
        last_seen_at=positives[-1].at,
        last_confirmed_at=last_confirmed_at,
        resolved_at=resolved_at,
    )
