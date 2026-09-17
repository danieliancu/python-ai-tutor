from apps.ai_tutor.constants import TurnStatus
from apps.ai_tutor.models import TutorTurn
from apps.learners.models import Enrollment


def recent_completed_turns(enrollment: Enrollment, limit: int) -> list[TutorTurn]:
    """The enrollment's latest completed turns, oldest first."""
    turns = list(
        TutorTurn.objects.filter(
            enrollment=enrollment, status=TurnStatus.COMPLETE, project__isnull=True
        ).order_by("-created_at", "-id")[:limit]
    )
    return turns[::-1]
