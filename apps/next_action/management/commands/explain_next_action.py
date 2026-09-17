import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.learners.models import Enrollment
from apps.next_action.engine import next_action_for_enrollment
from apps.next_action.presentation import decision_presentation


class Command(BaseCommand):
    help = (
        "Show the next best action for one enrollment (the same safe JSON the API returns, "
        "plus the internal priority tier and urgency). Read-only."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("enrollment_id", type=int)
        parser.add_argument("--now", help="Decide as of this ISO 8601 datetime.")

    def handle(self, *args, enrollment_id, now=None, **options) -> None:
        enrollment = Enrollment.objects.filter(pk=enrollment_id).first()
        if enrollment is None:
            raise CommandError(f"Enrollment {enrollment_id} does not exist.")
        moment = None
        if now is not None:
            moment = parse_datetime(now)
            if moment is None or moment.tzinfo is None:
                raise CommandError("--now must be an ISO 8601 datetime with a timezone.")
        decision = next_action_for_enrollment(enrollment, now=moment)
        payload = decision_presentation(decision, enrollment)
        payload["internal"] = {
            "priority_tier": decision.priority_tier,
            "urgency_score": decision.urgency_score,
        }
        self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
