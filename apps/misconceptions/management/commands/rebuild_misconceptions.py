from django.core.management.base import BaseCommand, CommandError

from apps.curriculum.models import World
from apps.learners.models import Enrollment
from apps.misconceptions.scoring import MISCONCEPTION_ALGORITHM_VERSION
from apps.misconceptions.services import rebuild_misconceptions


class Command(BaseCommand):
    help = (
        "Recalculate misconception evidence and states from attempt history and exercise "
        "metadata. Safe to run repeatedly."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--enrollment-id", type=int, help="Only rebuild this enrollment.")
        parser.add_argument("--world-slug", help="Only rebuild enrollments in this World.")

    def handle(self, *args, enrollment_id=None, world_slug=None, **options) -> None:
        if enrollment_id is not None and not Enrollment.objects.filter(pk=enrollment_id).exists():
            raise CommandError(f"Enrollment {enrollment_id} does not exist.")
        if world_slug is not None and not World.objects.filter(slug=world_slug).exists():
            raise CommandError(f"World '{world_slug}' does not exist.")

        stats = rebuild_misconceptions(enrollment_id=enrollment_id, world_slug=world_slug)
        self.stdout.write(
            f"Evidence: {stats['evidence_created']} created, {stats['evidence_updated']} updated, "
            f"{stats['evidence_deleted']} deleted"
        )
        self.stdout.write(
            f"States: {stats['states_created']} created, {stats['states_updated']} updated, "
            f"{stats['states_unchanged']} unchanged, {stats['states_deleted']} deleted "
            f"({stats['active']} active, {stats['watch']} watch, {stats['resolved']} resolved)"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Misconceptions rebuilt for {stats['pairs']} learner concepts "
                f"(algorithm v{MISCONCEPTION_ALGORITHM_VERSION})."
            )
        )
