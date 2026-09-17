"""Read-only queries over derived learner state."""

from datetime import datetime
from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from apps.curriculum.models import Concept, Skill
from apps.learner_intelligence.models import ConceptState, MasteryBand
from apps.learners.models import Enrollment


def concept_states_for_enrollment(enrollment: Enrollment) -> QuerySet[ConceptState]:
    return (
        ConceptState.objects.filter(enrollment=enrollment)
        .select_related("concept__skill")
        .prefetch_related("mode_states")
    )


def concept_state_for(enrollment: Enrollment, concept: Concept) -> ConceptState | None:
    return concept_states_for_enrollment(enrollment).filter(concept=concept).first()


def is_review_due(state: ConceptState | None, now: datetime | None = None) -> bool:
    """Derived on read: a stored boolean would go stale."""
    if state is None or state.review_due_at is None:
        return False
    return state.review_due_at <= (now or timezone.now())


def review_due_states(
    enrollment: Enrollment, now: datetime | None = None
) -> QuerySet[ConceptState]:
    return concept_states_for_enrollment(enrollment).filter(
        review_due_at__lte=now or timezone.now()
    )


def weak_concepts(enrollment: Enrollment) -> QuerySet[ConceptState]:
    return concept_states_for_enrollment(enrollment).filter(mastery_band=MasteryBand.WEAK)


def mastered_concepts(enrollment: Enrollment) -> QuerySet[ConceptState]:
    return concept_states_for_enrollment(enrollment).filter(mastery_band=MasteryBand.MASTERED)


def published_concepts_for_world(world_id: int) -> QuerySet[Concept]:
    return (
        Concept.objects.filter(
            is_published=True,
            skill__is_published=True,
            skill__world_id=world_id,
            skill__world__is_published=True,
        )
        .select_related("skill")
        .order_by("skill__order", "skill_id", "order", "id")
    )


def states_by_concept(enrollment: Enrollment, concepts: list[Concept]) -> dict[int, ConceptState]:
    states = concept_states_for_enrollment(enrollment).filter(concept__in=concepts)
    return {state.concept_id: state for state in states}


def summarise(
    concepts: list[Concept], states: dict[int, ConceptState], now: datetime | None = None
) -> dict:
    """Counts and average mastery; unstarted concepts count as mastery 0."""
    now = now or timezone.now()
    bands = {band: 0 for band in MasteryBand.values}
    total_mastery = Decimal("0")
    review_due = 0
    for concept in concepts:
        state = states.get(concept.pk)
        bands[state.mastery_band if state else MasteryBand.NOT_STARTED] += 1
        if state is not None:
            total_mastery += state.mastery_score
            review_due += is_review_due(state, now)
    mastery = (total_mastery / len(concepts)).quantize(Decimal("0.01")) if concepts else None
    return {
        "mastery": float(mastery) if mastery is not None else 0.0,
        "concepts_total": len(concepts),
        "concepts_started": len(concepts) - bands[MasteryBand.NOT_STARTED],
        "weak": bands[MasteryBand.WEAK],
        "learning": bands[MasteryBand.LEARNING],
        "practising": bands[MasteryBand.PRACTISING],
        "mastered": bands[MasteryBand.MASTERED],
        "review_due": review_due,
    }


def skill_summary(enrollment: Enrollment, skill: Skill, now: datetime | None = None) -> dict:
    concepts = [
        c for c in published_concepts_for_world(enrollment.world_id) if c.skill_id == skill.pk
    ]
    return summarise(concepts, states_by_concept(enrollment, concepts), now)


def world_summary(enrollment: Enrollment, now: datetime | None = None) -> dict:
    concepts = list(published_concepts_for_world(enrollment.world_id))
    return summarise(concepts, states_by_concept(enrollment, concepts), now)
