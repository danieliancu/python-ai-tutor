"""Safe misconception summaries for the Student State: codes, titles, status, confidence.

Evidence rows, detector internals, answers and exercise specs are never part of it.
"""

from apps.learners.models import Enrollment
from apps.misconceptions.definitions import title_for
from apps.misconceptions.models import MisconceptionState, MisconceptionStatus
from apps.misconceptions.selectors import misconceptions_for_world

VISIBLE_STATUSES = (MisconceptionStatus.ACTIVE, MisconceptionStatus.WATCH)


def misconception_item(state: MisconceptionState) -> dict:
    return {
        "code": state.code,
        "title": title_for(state.code),
        "status": state.status,
        "confidence": float(state.confidence_score),
    }


def misconception_overview(enrollment: Enrollment) -> dict[int, list[dict]]:
    """Active and watched misconceptions per concept id, active first, strongest first."""
    states = [
        state for state in misconceptions_for_world(enrollment) if state.status in VISIBLE_STATUSES
    ]
    # Stable sort: the queryset already orders strongest first.
    states.sort(key=lambda state: state.status != MisconceptionStatus.ACTIVE)
    by_concept: dict[int, list[dict]] = {}
    for state in states:
        by_concept.setdefault(state.concept_id, []).append(misconception_item(state))
    return by_concept
