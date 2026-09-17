from datetime import date, datetime, time

from django.utils import timezone

from apps.attempts.tests.helpers import SECRET_NUMBER, SECRET_OPTION, AttemptFixtures
from apps.gamification.models import XPEvent
from apps.learner_intelligence.models import ConceptState, MasteryBand


def at_noon(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(12, 0)))


class GamificationFixtures(AttemptFixtures):
    """AttemptFixtures plus shortcuts for correct and wrong answers."""

    def correct_mcq(self, **kwargs):
        return self.record(self.mcq, SECRET_OPTION, **kwargs)

    def wrong_mcq(self, **kwargs):
        return self.record(self.mcq, "opt-a", **kwargs)

    def correct_numeric(self, **kwargs):
        return self.record(self.numeric, SECRET_NUMBER, **kwargs)

    def events(self, **filters) -> list[tuple[str, int]]:
        return list(
            XPEvent.objects.filter(learner=self.profile, **filters)
            .order_by("id")
            .values_list("event_type", "xp")
        )

    def master_skill(self, enrollment, skill) -> None:
        for concept in skill.concepts.all():
            ConceptState.objects.update_or_create(
                enrollment=enrollment,
                concept=concept,
                defaults={
                    "mastery_band": MasteryBand.MASTERED,
                    "mastery_score": 95,
                    "evidence_count": 5,
                },
            )

    @staticmethod
    def move_to(attempt, day: date) -> None:
        type(attempt).objects.filter(pk=attempt.pk).update(submitted_at=at_noon(day))
