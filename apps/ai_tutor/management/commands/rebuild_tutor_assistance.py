from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.ai_tutor.assistance import reconcile_outcome
from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment


class Command(BaseCommand):
    help = (
        "Rebuild per-exercise AI help records from completed tutor turns and attempts. "
        "Safe to run repeatedly; reads repair records automatically too."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--enrollment-id", type=int, help="Only rebuild this enrollment.")

    def handle(self, *args, enrollment_id=None, **options) -> None:
        states = TutorExerciseState.objects.all()
        turns = TutorTurn.objects.filter(exercise__isnull=False)
        if enrollment_id is not None:
            if not Enrollment.objects.filter(pk=enrollment_id).exists():
                raise CommandError(f"Enrollment {enrollment_id} does not exist.")
            states = states.filter(enrollment_id=enrollment_id)
            turns = turns.filter(enrollment_id=enrollment_id)

        pairs = set(states.values_list("enrollment_id", "exercise_id")) | set(
            turns.order_by().values_list("enrollment_id", "exercise_id").distinct()
        )
        enrollments = Enrollment.objects.in_bulk({e for e, _ in pairs})
        exercises = Exercise.objects.in_bulk({x for _, x in pairs})
        stats = Counter({"created": 0, "updated": 0, "unchanged": 0})
        for enrollment_pk, exercise_pk in sorted(pairs):
            outcome = reconcile_outcome(enrollments[enrollment_pk], exercises[exercise_pk])
            stats[outcome] += 1
        self.stdout.write(
            f"Tutor assistance: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['unchanged']} unchanged ({len(pairs)} total)"
        )
