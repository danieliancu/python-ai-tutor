"""Student State: the structured learning picture future tutoring will consume.

An explicit allow-list of derived signals. Answers, evaluation specs and diagnostics are never
part of it.
"""

from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from apps.exercises.models import LearningMode
from apps.learner_intelligence.models import ConceptState, MasteryBand, Trend
from apps.learner_intelligence.selectors import (
    is_review_due,
    published_concepts_for_world,
    states_by_concept,
    summarise,
)
from apps.learners.models import Enrollment


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def concept_signals(concept, state: ConceptState | None, now: datetime) -> dict:
    modes = {}
    if state is not None:
        by_mode = {row.learning_mode: row for row in state.mode_states.all()}
        modes = {
            mode: float(by_mode[mode].performance_score)
            for mode in LearningMode.values
            if mode in by_mode
        }
    return {
        "concept_id": concept.pk,
        "skill_id": concept.skill_id,
        "title": concept.title,
        "mastery": float(state.mastery_score) if state else 0.0,
        "band": state.mastery_band if state else MasteryBand.NOT_STARTED.value,
        "retention": _number(state.retention_score) if state else None,
        "independence": _number(state.independence_score) if state else None,
        "fluency": _number(state.fluency_score) if state else None,
        "trend": state.trend if state else Trend.INSUFFICIENT_DATA.value,
        "evidence_count": state.evidence_count if state else 0,
        "correct_count": state.correct_count if state else 0,
        "stability_days": state.stability_days if state else None,
        "last_attempt_at": _iso(state.last_attempt_at) if state else None,
        "review_due_at": _iso(state.review_due_at) if state else None,
        "review_due": is_review_due(state, now),
        "modes": modes,
    }


def concept_misconceptions(enrollment: Enrollment) -> dict[int, list[dict]]:
    """Active and watched misconceptions per concept (safe summaries only)."""
    # Local import keeps the dependency one-way at import time: misconceptions builds on
    # learner intelligence scoring, and only this presentation layer reads it back.
    from apps.misconceptions.presentation import misconception_overview

    return misconception_overview(enrollment)


def student_state_for_enrollment(enrollment: Enrollment, *, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    concepts = list(published_concepts_for_world(enrollment.world_id))
    states = states_by_concept(enrollment, concepts)

    skills: dict[int, dict] = {}
    for concept in concepts:
        skills.setdefault(concept.skill_id, {"skill": concept.skill, "concepts": []})
        skills[concept.skill_id]["concepts"].append(concept)

    misconceptions = concept_misconceptions(enrollment)
    visible = [item for c in concepts for item in misconceptions.get(c.pk, [])]

    return {
        "world_id": enrollment.world_id,
        "generated_at": now.isoformat(),
        "summary": {
            **summarise(concepts, states, now),
            "active_misconceptions": sum(i["status"] == "active" for i in visible),
            "watch_misconceptions": sum(i["status"] == "watch" for i in visible),
        },
        "skills": [
            {
                "skill_id": skill_id,
                "title": group["skill"].title,
                **summarise(group["concepts"], states, now),
            }
            for skill_id, group in skills.items()
        ],
        "concepts": [
            {
                **concept_signals(c, states.get(c.pk), now),
                "misconceptions": misconceptions.get(c.pk, []),
            }
            for c in concepts
        ],
    }
