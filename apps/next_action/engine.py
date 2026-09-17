"""Next Best Action: what should this learner do next in this World?

Computed on demand from the learner's current derived state; nothing is stored. The same data
and the same ``now`` always give the same decision.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from django.db.models import Count
from django.utils import timezone

from apps.attempts.models import ExerciseAttempt
from apps.curriculum.models import Concept, ConceptPrerequisite, SkillPrerequisite
from apps.exercises.models import Exercise
from apps.exercises.selectors import published_exercises
from apps.learner_intelligence.selectors import (
    concept_states_for_enrollment,
    published_concepts_for_world,
)
from apps.learners.models import Enrollment
from apps.misconceptions.models import MisconceptionStatus
from apps.misconceptions.selectors import misconceptions_for_world
from apps.next_action import constants as c
from apps.next_action.candidates import candidate_for, is_course_complete, rank_candidates
from apps.next_action.exercise_picker import pick_exercise
from apps.next_action.prerequisites import (
    concept_prerequisites_ready,
    skill_prerequisites_ready,
)
from apps.next_action.types import ActiveMisconception, ConceptContext, NextActionDecision


@dataclass
class _WorldSnapshot:
    """The learner's world, loaded with a fixed number of queries."""

    concepts: list[Concept]
    exercises_by_concept: dict[int, list[Exercise]]
    contexts: list[ConceptContext]
    attempt_counts: dict[int, int]
    blocked: list[int] = field(default_factory=list)


def next_action_for_enrollment(
    enrollment: Enrollment, *, now: datetime | None = None
) -> NextActionDecision:
    now = now or timezone.now()
    snapshot = _load(enrollment)

    def decision(action, primary, reasons, **fields) -> NextActionDecision:
        return NextActionDecision(
            algorithm_version=c.NEXT_ACTION_ALGORITHM_VERSION,
            action_type=action,
            world_id=enrollment.world_id,
            primary_reason=primary,
            reason_codes=tuple(dict.fromkeys((primary, *reasons))),
            generated_at=now,
            **fields,
        )

    if not snapshot.concepts:
        return decision(c.NO_AVAILABLE_ACTION, c.NO_PUBLISHED_CONTENT, ())

    candidates = rank_candidates(
        candidate
        for context in snapshot.contexts
        if (candidate := candidate_for(context, now)) is not None
    )
    if is_course_complete(snapshot.contexts, now):
        return decision(c.COURSE_COMPLETE, c.WORLD_COMPLETE, ())

    contexts = {context.concept_id: context for context in snapshot.contexts}
    concepts = {concept.pk: concept for concept in snapshot.concepts}
    missing_exercises = False
    for candidate in candidates:
        context = contexts[candidate.concept_id]
        exercises = snapshot.exercises_by_concept.get(candidate.concept_id, [])
        pick = pick_exercise(
            exercises,
            action=candidate.action_type,
            context=context,
            attempt_counts=snapshot.attempt_counts,
            recent_ids=_recent_exercise_ids(enrollment, candidate.concept_id) if exercises else (),
            active_codes=candidate.misconception_codes
            if candidate.action_type == c.REMEDIATE
            else (),
        )
        if pick is None:
            missing_exercises = True
            continue
        reasons = list(candidate.reason_codes)
        if pick.remediation_fallback:
            reasons.append(c.REMEDIATION_FALLBACK)
        return decision(
            candidate.action_type,
            candidate.reason_codes[0],
            reasons,
            skill_id=concepts[candidate.concept_id].skill_id,
            concept_id=candidate.concept_id,
            lesson_id=pick.exercise.lesson_id,
            exercise_id=pick.exercise.pk,
            target_learning_mode=pick.target_mode,
            misconception_codes=candidate.misconception_codes,
            priority_tier=candidate.priority_tier,
            urgency_score=candidate.urgency_score,
        )

    # Nothing actionable. Never call a blocked or incomplete World "complete".
    if not all(context.has_exercises for context in snapshot.contexts):
        missing_exercises = True
    reasons = []
    if snapshot.blocked:
        reasons.append(c.BLOCKED_BY_PREREQUISITES)
    if missing_exercises:
        reasons.append(c.NO_PUBLISHED_EXERCISE)
    primary = reasons[0] if reasons else c.BLOCKED_BY_PREREQUISITES
    return decision(c.NO_AVAILABLE_ACTION, primary, reasons)


def _recent_exercise_ids(enrollment: Enrollment, concept_id: int) -> list[int]:
    return list(
        ExerciseAttempt.objects.filter(
            enrollment=enrollment, exercise__lesson__concept_id=concept_id
        )
        .order_by("-submitted_at", "-id")
        .values_list("exercise_id", flat=True)[: c.RECENT_EXERCISE_COOLDOWN]
    )


def _load(enrollment: Enrollment) -> _WorldSnapshot:
    concepts = list(published_concepts_for_world(enrollment.world_id))
    if not concepts:
        return _WorldSnapshot(concepts=[], exercises_by_concept={}, contexts=[], attempt_counts={})
    concept_ids = [concept.pk for concept in concepts]
    skill_ids = {concept.skill_id for concept in concepts}

    concept_prereqs = defaultdict(list)
    for concept_id, prerequisite_id in ConceptPrerequisite.objects.filter(
        concept_id__in=concept_ids
    ).values_list("concept_id", "prerequisite_id"):
        concept_prereqs[concept_id].append(prerequisite_id)
    skill_prereqs = defaultdict(list)
    for skill_id, prerequisite_id in SkillPrerequisite.objects.filter(
        skill_id__in=skill_ids
    ).values_list("skill_id", "prerequisite_id"):
        skill_prereqs[skill_id].append(prerequisite_id)

    # All of this enrollment's states: prerequisites may sit outside the published set.
    states = {state.concept_id: state for state in concept_states_for_enrollment(enrollment)}
    mastery = {pk: float(state.mastery_score) for pk, state in states.items()}

    active = defaultdict(list)
    watch = defaultdict(list)
    for state in misconceptions_for_world(enrollment):  # strongest first
        if state.status == MisconceptionStatus.ACTIVE:
            active[state.concept_id].append(
                ActiveMisconception(state.code, float(state.confidence_score), state.last_seen_at)
            )
        elif state.status == MisconceptionStatus.WATCH:
            watch[state.concept_id].append(state.code)

    attempts = ExerciseAttempt.objects.filter(enrollment=enrollment)
    attempted_concepts = set(
        # order_by() clears the default ordering, which would otherwise break distinct().
        attempts.order_by().values_list("exercise__lesson__concept_id", flat=True).distinct()
    )
    latest = (
        attempts.order_by("-submitted_at", "-id")
        .values_list("exercise__lesson__concept_id", flat=True)
        .first()
    )
    attempt_counts = dict(
        attempts.values("exercise_id")
        .annotate(total=Count("id"))
        .order_by()
        .values_list("exercise_id", "total")
    )

    exercises_by_concept = defaultdict(list)
    for exercise in (
        published_exercises()
        .filter(lesson__concept_id__in=concept_ids)
        .select_related("lesson")
        .order_by("lesson__concept_id", "lesson__order", "order", "id")
    ):
        exercises_by_concept[exercise.lesson.concept_id].append(exercise)

    published_by_skill = defaultdict(list)
    for concept in concepts:
        published_by_skill[concept.skill_id].append(concept.pk)

    contexts = []
    blocked = []
    for concept in concepts:
        state = states.get(concept.pk)
        started = state is not None or concept.pk in attempted_concepts
        modes = list(state.mode_states.all()) if state else []
        ready = concept_prerequisites_ready(
            concept_prereqs[concept.pk], mastery
        ) and skill_prerequisites_ready(
            skill_prereqs[concept.skill_id], published_by_skill, mastery
        )
        available = frozenset(e.learning_mode for e in exercises_by_concept[concept.pk])
        if not started and available and not ready:
            blocked.append(concept.pk)
        contexts.append(
            ConceptContext(
                concept_id=concept.pk,
                skill_id=concept.skill_id,
                skill_order=concept.skill.order,
                concept_order=concept.order,
                started=started,
                has_state=state is not None,
                mastery=float(state.mastery_score) if state else 0.0,
                band=state.mastery_band if state else "not_started",
                trend=state.trend if state else "insufficient_data",
                retention=float(state.retention_score)
                if state and state.retention_score is not None
                else None,
                review_due_at=state.review_due_at if state else None,
                active_misconceptions=tuple(active[concept.pk]),
                watch_codes=tuple(watch[concept.pk]),
                mode_success=frozenset(m.learning_mode for m in modes if m.correct_count > 0),
                mode_performance={m.learning_mode: float(m.performance_score) for m in modes},
                mode_independence={
                    m.learning_mode: float(m.independence_score)
                    for m in modes
                    if m.independence_score is not None
                },
                available_modes=available,
                prerequisites_ready=ready,
                is_most_recent=concept.pk == latest,
            )
        )
    return _WorldSnapshot(
        concepts=concepts,
        exercises_by_concept=dict(exercises_by_concept),
        contexts=contexts,
        attempt_counts=attempt_counts,
        blocked=blocked,
    )


def concept_contexts(enrollment: Enrollment) -> list[ConceptContext]:
    """The per-concept facts the engine decides from (read-only; for presentation layers)."""
    return _load(enrollment).contexts
