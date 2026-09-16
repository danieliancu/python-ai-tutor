from django.db.models import Prefetch, QuerySet

from apps.curriculum.models import Concept, Lesson, Skill, World


def published_curriculum() -> QuerySet[World]:
    """Published Worlds with their published Skills → Concepts → Lessons prefetched.

    Walking ``world.skills.all()`` → ``skill.concepts.all()`` → ``concept.lessons.all()``
    costs four queries in total, whatever the size of the tree. Children of an unpublished
    parent are never reached.
    """
    lessons = Lesson.objects.filter(is_published=True).order_by("order", "id")
    concepts = (
        Concept.objects.filter(is_published=True)
        .order_by("order", "id")
        .prefetch_related(Prefetch("lessons", queryset=lessons))
    )
    skills = (
        Skill.objects.filter(is_published=True)
        .order_by("order", "id")
        .prefetch_related(Prefetch("concepts", queryset=concepts))
    )
    return (
        World.objects.filter(is_published=True)
        .order_by("order", "id")
        .prefetch_related(Prefetch("skills", queryset=skills))
    )
