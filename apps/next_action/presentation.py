"""The public view of a decision: an explicit allow-list.

Ranking internals (tiers, urgency), exercise specs, tags, evidence and answers never appear.
"""

from apps.exercises.models import Exercise
from apps.exercises.presentation import exercise_presentation
from apps.misconceptions.models import MisconceptionState, MisconceptionStatus
from apps.misconceptions.presentation import misconception_item
from apps.next_action.types import NextActionDecision

PUBLIC_MISCONCEPTION_STATUSES = (MisconceptionStatus.ACTIVE, MisconceptionStatus.WATCH)


def decision_presentation(decision: NextActionDecision, enrollment) -> dict:
    exercise = None
    if decision.exercise_id is not None:
        exercise = Exercise.objects.select_related("lesson__concept__skill").get(
            pk=decision.exercise_id
        )
    lesson = exercise.lesson if exercise else None
    concept = lesson.concept if lesson else None
    skill = concept.skill if concept else None

    misconceptions = []
    if decision.misconception_codes and decision.concept_id is not None:
        states = {
            state.code: state
            for state in MisconceptionState.objects.filter(
                enrollment=enrollment,
                concept_id=decision.concept_id,
                code__in=decision.misconception_codes,
                status__in=PUBLIC_MISCONCEPTION_STATUSES,
            )
        }
        misconceptions = [
            misconception_item(states[code])
            for code in decision.misconception_codes
            if code in states
        ]

    return {
        "algorithm_version": decision.algorithm_version,
        "action": decision.action_type,
        "primary_reason": decision.primary_reason,
        "reason_codes": list(decision.reason_codes),
        "world_id": decision.world_id,
        "skill": {"id": skill.pk, "title": skill.title} if skill else None,
        "concept": {"id": concept.pk, "title": concept.title} if concept else None,
        "lesson": (
            {"id": lesson.pk, "title": lesson.title, "kind": lesson.kind} if lesson else None
        ),
        "exercise": exercise_presentation(exercise) if exercise else None,
        "target_learning_mode": decision.target_learning_mode,
        "misconceptions": misconceptions,
        "generated_at": decision.generated_at.isoformat(),
    }
