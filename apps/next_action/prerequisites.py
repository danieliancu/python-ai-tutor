"""Readiness to introduce new concepts. Only LEARN is gated; started concepts never lock."""

from collections.abc import Iterable, Mapping

from apps.next_action.constants import PREREQUISITE_MASTERY_THRESHOLD


def is_ready(mastery_by_concept: Mapping[int, float], concept_id: int) -> bool:
    """A concept is ready when its derived mastery reaches the threshold (no state: not ready)."""
    mastery = mastery_by_concept.get(concept_id)
    return mastery is not None and mastery >= PREREQUISITE_MASTERY_THRESHOLD


def concept_prerequisites_ready(
    prerequisite_ids: Iterable[int], mastery_by_concept: Mapping[int, float]
) -> bool:
    return all(is_ready(mastery_by_concept, pk) for pk in prerequisite_ids)


def skill_prerequisites_ready(
    prerequisite_skill_ids: Iterable[int],
    published_concepts_by_skill: Mapping[int, Iterable[int]],
    mastery_by_concept: Mapping[int, float],
) -> bool:
    """Every published concept of every prerequisite skill must be ready.

    A prerequisite skill without published concepts is unsatisfied rather than skipped, so a
    curriculum gap never silently unlocks later content.
    """
    for skill_id in prerequisite_skill_ids:
        concept_ids = list(published_concepts_by_skill.get(skill_id, ()))
        if not concept_ids or not concept_prerequisites_ready(concept_ids, mastery_by_concept):
            return False
    return True
