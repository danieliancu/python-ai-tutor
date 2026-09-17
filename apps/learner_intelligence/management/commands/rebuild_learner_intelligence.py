from django.core.management.base import BaseCommand, CommandError

from apps.curriculum.models import World
from apps.learner_intelligence.scoring import ALGORITHM_VERSION
from apps.learner_intelligence.services import rebuild_learner_intelligence
from apps.learners.models import Enrollment


class Command(BaseCommand):
    help = (
        "Recalculate learner intelligence (concept and mode states) from attempt history. "
        "Safe to run repeatedly; states without attempts are removed."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--enrollment-id", type=int, help="Only rebuild this enrollment.")
        parser.add_argument("--world-slug", help="Only rebuild enrollments in this World.")

    def handle(self, *args, enrollment_id=None, world_slug=None, **options) -> None:
        if enrollment_id is not None and not Enrollment.objects.filter(pk=enrollment_id).exists():
            raise CommandError(f"Enrollment {enrollment_id} does not exist.")
        if world_slug is not None and not World.objects.filter(slug=world_slug).exists():
            raise CommandError(f"World '{world_slug}' does not exist.")

        stats = rebuild_learner_intelligence(enrollment_id=enrollment_id, world_slug=world_slug)
        self.stdout.write(
            f"Concept states: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['unchanged']} unchanged, {stats['deleted']} stale deleted "
            f"({stats['total']} total)"
        )
        self.stdout.write(
            self.style.SUCCESS(f"Learner intelligence rebuilt (algorithm v{ALGORITHM_VERSION}).")
        )
