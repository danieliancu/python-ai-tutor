"""Recalculate derived learner state from attempt history.

State is never incremented: every refresh recomputes from ``ExerciseAttempt`` rows, so
running it again without new attempts leaves the stored values unchanged.
"""

from collections import Counter
from dataclasses import replace
from datetime import datetime

from django.db import transaction
from django.db.models import Count, Max, Q

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.curriculum.models import Concept
from apps.learner_intelligence import scoring
from apps.learner_intelligence.models import ConceptModeState, ConceptState
from apps.learners.models import Enrollment

CREATED = "created"
UPDATED = "updated"
UNCHANGED = "unchanged"
DELETED = "deleted"

JUDGED = list(scoring.JUDGED_STATUSES)


def refresh_concept_state(
    enrollment: Enrollment, concept: Concept, *, now: datetime | None = None
) -> ConceptState | None:
    """Recompute one learner's state for one concept. None if there is no attempt history.

    Stored values depend only on attempt history, never on the clock (review dues are derived
    from ``review_due_at`` when presenting); ``now`` is accepted for a uniform service API.
    """
    state, _ = _refresh(enrollment, concept)
    return state


def refresh_for_attempt(attempt: ExerciseAttempt) -> ConceptState | None:
    return refresh_concept_state(attempt.enrollment, attempt.exercise.lesson.concept)


def rebuild_learner_intelligence(
    *, enrollment_id: int | None = None, world_slug: str | None = None
) -> Counter:
    """Rebuild every state represented by attempts (optionally filtered). Safe to repeat."""
    attempts = ExerciseAttempt.objects.all()
    states = ConceptState.objects.all()
    if enrollment_id is not None:
        attempts = attempts.filter(enrollment_id=enrollment_id)
        states = states.filter(enrollment_id=enrollment_id)
    if world_slug is not None:
        attempts = attempts.filter(enrollment__world__slug=world_slug)
        states = states.filter(enrollment__world__slug=world_slug)

    pairs = set(attempts.values_list("enrollment_id", "exercise__lesson__concept_id").distinct())
    enrollments = Enrollment.objects.in_bulk({enrollment for enrollment, _ in pairs})
    concepts = Concept.objects.in_bulk({concept for _, concept in pairs})

    stats = Counter({CREATED: 0, UPDATED: 0, UNCHANGED: 0, DELETED: 0})
    for enrollment_pk, concept_pk in sorted(pairs):
        _, outcome = _refresh(enrollments[enrollment_pk], concepts[concept_pk])
        stats[outcome] += 1

    stale = [
        state.pk
        for state in states.only("pk", "enrollment_id", "concept_id")
        if (state.enrollment_id, state.concept_id) not in pairs
    ]
    if stale:
        ConceptState.objects.filter(pk__in=stale).delete()
        stats[DELETED] += len(stale)
    stats["total"] = len(pairs)
    return stats


def _load_evidence(enrollment: Enrollment, concept: Concept):
    attempts = ExerciseAttempt.objects.filter(
        enrollment=enrollment, exercise__lesson__concept=concept
    )
    judged_attempts = (
        attempts.filter(status__in=JUDGED)
        .select_related("exercise")
        .order_by("-submitted_at", "-id")[: scoring.RETENTION_HISTORY_LIMIT]
    )
    evidence = [scoring.Evidence.from_attempt(attempt) for attempt in judged_attempts]
    totals = attempts.aggregate(
        last_attempt_at=Max("submitted_at"),
        judged=Count("id", filter=Q(status__in=JUDGED)),
        correct=Count("id", filter=Q(status=AttemptStatus.CORRECT)),
    )
    mode_totals = {
        row["exercise__learning_mode"]: row
        for row in attempts.filter(status__in=JUDGED)
        .values("exercise__learning_mode")
        .annotate(judged=Count("id"), correct=Count("id", filter=Q(status=AttemptStatus.CORRECT)))
        .order_by()
    }
    return evidence, totals, mode_totals


@transaction.atomic
def _refresh(enrollment: Enrollment, concept: Concept) -> tuple[ConceptState | None, str]:
    evidence, totals, mode_totals = _load_evidence(enrollment, concept)
    existing = ConceptState.objects.filter(enrollment=enrollment, concept=concept).first()
    if totals["last_attempt_at"] is None:
        if existing is None:
            return None, UNCHANGED
        existing.delete()
        return None, DELETED

    metrics = scoring.compute_concept_metrics(evidence)
    # Counts cover the whole history, not just the bounded evidence window.
    metrics = replace(metrics, evidence_count=totals["judged"], correct_count=totals["correct"])

    values = {
        "mastery_score": scoring.round_score(metrics.mastery),
        "mastery_band": metrics.band,
        "retention_score": scoring.round_score(metrics.retention),
        "independence_score": scoring.round_score(metrics.independence),
        "fluency_score": scoring.round_score(metrics.fluency),
        "trend": metrics.trend,
        "trend_score": scoring.round_score(metrics.trend_score, -1.0, 1.0),
        "stability_days": metrics.stability_days,
        "review_due_at": metrics.review_due_at,
        "evidence_count": metrics.evidence_count,
        "correct_count": metrics.correct_count,
        "retention_evidence_count": metrics.retention_evidence_count,
        "last_attempt_at": totals["last_attempt_at"],
        "last_success_at": metrics.last_success_at,
        "algorithm_version": scoring.ALGORITHM_VERSION,
    }
    state, outcome = _upsert(ConceptState, existing, values, enrollment=enrollment, concept=concept)
    if _sync_modes(state, metrics.modes, mode_totals) and outcome == UNCHANGED:
        outcome = UPDATED
    return state, outcome


def _sync_modes(state: ConceptState, modes: dict, mode_totals: dict) -> bool:
    """Match mode rows to the modes with judged evidence. True if anything changed."""
    changed = False
    existing = {row.learning_mode: row for row in state.mode_states.all()}
    for mode, metrics in modes.items():
        totals = mode_totals.get(mode, {})
        values = {
            "performance_score": scoring.round_score(metrics.performance),
            "attempt_count": totals.get("judged", metrics.attempt_count),
            "correct_count": totals.get("correct", metrics.correct_count),
            "independence_score": scoring.round_score(metrics.independence),
            "fluency_score": scoring.round_score(metrics.fluency),
            "last_attempt_at": metrics.last_attempt_at,
        }
        _, outcome = _upsert(
            ConceptModeState,
            existing.pop(mode, None),
            values,
            concept_state=state,
            learning_mode=mode,
        )
        changed |= outcome != UNCHANGED
    if existing:
        ConceptModeState.objects.filter(pk__in=[row.pk for row in existing.values()]).delete()
        changed = True
    return changed


def _upsert(model, instance, values: dict, **identity):
    """Create, or update only when a value differs (so ``updated_at`` stays meaningful)."""
    if instance is None:
        return model.objects.create(**identity, **values), CREATED
    if all(getattr(instance, name) == value for name, value in values.items()):
        return instance, UNCHANGED
    for name, value in values.items():
        setattr(instance, name, value)
    instance.save()
    return instance, UPDATED
