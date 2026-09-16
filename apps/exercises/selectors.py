from django.db.models import QuerySet

from apps.curriculum.models import Lesson
from apps.exercises.models import Exercise


def published_exercises() -> QuerySet[Exercise]:
    """Exercises that are published and whose Lesson, Concept, Skill and World are too."""
    return Exercise.objects.filter(
        is_published=True,
        lesson__is_published=True,
        lesson__concept__is_published=True,
        lesson__concept__skill__is_published=True,
        lesson__concept__skill__world__is_published=True,
    )


def published_exercises_for_lesson(lesson: Lesson) -> QuerySet[Exercise]:
    return published_exercises().filter(lesson=lesson).order_by("order", "id")
