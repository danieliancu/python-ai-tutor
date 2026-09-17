from django.core.management.base import BaseCommand, CommandError

from apps.gamification.services import rebuild_gamification
from apps.learners.models import Enrollment, LearnerProfile


class Command(BaseCommand):
    help = (
        "Rebuild XP, levels, streaks, boss completions and achievements from attempt history "
        "and learner intelligence. Safe to run repeatedly; nothing is awarded twice."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--learner-id", type=int, help="Only rebuild this learner profile.")
        parser.add_argument("--enrollment-id", type=int, help="Only rebuild this enrollment.")

    def handle(self, *args, learner_id=None, enrollment_id=None, **options) -> None:
        if learner_id is not None and not LearnerProfile.objects.filter(pk=learner_id).exists():
            raise CommandError(f"Learner profile {learner_id} does not exist.")
        if enrollment_id is not None and not Enrollment.objects.filter(pk=enrollment_id).exists():
            raise CommandError(f"Enrollment {enrollment_id} does not exist.")

        stats = rebuild_gamification(learner_id=learner_id, enrollment_id=enrollment_id)
        self.stdout.write(
            f"Learners: {stats['learners']}; XP events created: {stats['xp_events_created']}; "
            f"achievements awarded: {stats['awards_created']}"
        )
        self.stdout.write(self.style.SUCCESS("Gamification rebuilt."))
