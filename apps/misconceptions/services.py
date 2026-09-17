"""Recalculate misconception evidence and state from attempt history.

Nothing is incremented: every refresh re-runs the detectors over the stored attempts, so
repeating it without new attempts leaves every row unchanged.
"""

import logging
from collections import Counter
from decimal import Decimal

from django.db import transaction

from apps.attempts.models import ExerciseAttempt
from apps.curriculum.models import Concept
from apps.learners.models import Enrollment
from apps.misconceptions import registry, scoring
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState

logger = logging.getLogger(__name__)


def refresh_concept_misconceptions(
    enrollment: Enrollment, concept: Concept, *, stats: Counter | None = None
) -> list[MisconceptionState]:
    """Recompute one learner's evidence and states for one concept."""
    stats = stats if stats is not None else Counter()
    with transaction.atomic():
        attempts = _recent_attempts(enrollment, concept)
        _sync_evidence(enrollment, concept, attempts, stats)
        return _sync_states(enrollment, concept, stats)


def refresh_for_attempt(attempt: ExerciseAttempt) -> list[MisconceptionState]:
    return refresh_concept_misconceptions(attempt.enrollment, attempt.exercise.lesson.concept)


def rebuild_misconceptions(
    *, enrollment_id: int | None = None, world_slug: str | None = None
) -> Counter:
    """Rebuild evidence and states for every enrollment/concept with attempts. Repeatable."""
    attempts = ExerciseAttempt.objects.all()
    states = MisconceptionState.objects.all()
    if enrollment_id is not None:
        attempts = attempts.filter(enrollment_id=enrollment_id)
        states = states.filter(enrollment_id=enrollment_id)
    if world_slug is not None:
        attempts = attempts.filter(enrollment__world__slug=world_slug)
        states = states.filter(enrollment__world__slug=world_slug)

    pairs = set(attempts.values_list("enrollment_id", "exercise__lesson__concept_id").distinct())
    enrollments = Enrollment.objects.in_bulk({enrollment for enrollment, _ in pairs})
    concepts = Concept.objects.in_bulk({concept for _, concept in pairs})

    stats = Counter()
    for enrollment_pk, concept_pk in sorted(pairs):
        refresh_concept_misconceptions(
            enrollments[enrollment_pk], concepts[concept_pk], stats=stats
        )

    stale = [
        state.pk
        for state in states.only("pk", "enrollment_id", "concept_id")
        if (state.enrollment_id, state.concept_id) not in pairs
    ]
    if stale:
        MisconceptionState.objects.filter(pk__in=stale).delete()
        stats["states_deleted"] += len(stale)

    for status in scoring.ACTIVE, scoring.WATCH, scoring.RESOLVED:
        stats[status] = states.filter(status=status).count()
    stats["pairs"] = len(pairs)
    return stats


def _recent_attempts(enrollment: Enrollment, concept: Concept) -> list[ExerciseAttempt]:
    return list(
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise__lesson__concept=concept)
        .select_related("exercise")
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")[: scoring.MISCONCEPTION_HISTORY_LIMIT]
    )


def _detect(attempt: ExerciseAttempt) -> dict[tuple, tuple[Decimal, dict]]:
    signals = {}
    for detector in registry.detectors():
        try:
            found = detector.detect(attempt)
        except Exception as exc:
            # Never log answers or source code: ids, detector and exception class only.
            logger.error(
                "Misconception detector %s failed on attempt %s (exercise %s): %s",
                detector.name,
                attempt.pk,
                attempt.exercise_id,
                type(exc).__name__,
            )
            continue
        for signal in found:
            key = (attempt.pk, signal.code, signal.kind, signal.source)
            strength = Decimal(repr(signal.strength)).quantize(scoring.TWO_PLACES)
            signals[key] = (strength, dict(signal.details))
    return signals


def _sync_evidence(enrollment, concept, attempts, stats: Counter) -> None:
    desired: dict[tuple, tuple[Decimal, dict]] = {}
    for attempt in attempts:
        desired.update(_detect(attempt))

    existing = MisconceptionEvidence.objects.filter(
        attempt__enrollment=enrollment, attempt__exercise__lesson__concept=concept
    )
    stale = []
    for row in existing:
        key = (row.attempt_id, row.code, row.kind, row.source)
        wanted = desired.pop(key, None)
        if wanted is None:
            stale.append(row.pk)
            continue
        strength, details = wanted
        if row.strength != strength or row.details != details:
            row.strength, row.details = strength, details
            row.save()
            stats["evidence_updated"] += 1
    if stale:
        MisconceptionEvidence.objects.filter(pk__in=stale).delete()
        stats["evidence_deleted"] += len(stale)
    for (attempt_id, code, kind, source), (strength, details) in desired.items():
        MisconceptionEvidence.objects.create(
            attempt_id=attempt_id,
            code=code,
            kind=kind,
            source=source,
            strength=strength,
            details=details,
        )
        stats["evidence_created"] += 1


def _evidence_rows(enrollment, concept) -> list[scoring.EvidenceRow]:
    rows = (
        MisconceptionEvidence.objects.filter(
            attempt__enrollment=enrollment, attempt__exercise__lesson__concept=concept
        )
        .order_by()
        .values_list(
            "attempt_id",
            "attempt__exercise_id",
            "attempt__submitted_at",
            "code",
            "kind",
            "strength",
        )
    )
    return [
        scoring.EvidenceRow(attempt_id, exercise_id, at, code, kind, float(strength))
        for attempt_id, exercise_id, at, code, kind, strength in rows
    ]


def _sync_states(enrollment, concept, stats: Counter) -> list[MisconceptionState]:
    grouped = scoring.group_attempt_evidence(_evidence_rows(enrollment, concept))
    existing = {
        state.code: state
        for state in MisconceptionState.objects.filter(enrollment=enrollment, concept=concept)
    }
    states = []
    for code in sorted(grouped):
        summary = scoring.aggregate_misconception(grouped[code])
        if summary is None:
            continue
        values = {
            "status": summary.status,
            "confidence_score": scoring.round_confidence(summary.confidence),
            "positive_evidence_count": summary.positive_evidence_count,
            "counter_evidence_count": summary.counter_evidence_count,
            "strong_evidence_count": summary.strong_evidence_count,
            "distinct_exercise_count": summary.distinct_exercise_count,
            "first_seen_at": summary.first_seen_at,
            "last_seen_at": summary.last_seen_at,
            "last_confirmed_at": summary.last_confirmed_at,
            "resolved_at": summary.resolved_at,
            "algorithm_version": scoring.MISCONCEPTION_ALGORITHM_VERSION,
        }
        state = existing.pop(code, None)
        if state is None:
            state = MisconceptionState.objects.create(
                enrollment=enrollment, concept=concept, code=code, **values
            )
            stats["states_created"] += 1
        elif any(getattr(state, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(state, name, value)
            state.save()
            stats["states_updated"] += 1
        else:
            stats["states_unchanged"] += 1
        states.append(state)
    if existing:
        MisconceptionState.objects.filter(pk__in=[s.pk for s in existing.values()]).delete()
        stats["states_deleted"] += len(existing)
    return states
