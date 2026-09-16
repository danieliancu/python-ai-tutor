"""Small builders for curriculum tests. Orders and slugs default to the next free value."""

from itertools import count

from apps.curriculum.models import Concept, Lesson, Skill, World

_sequence = count(1)


def _next() -> int:
    return next(_sequence)


def make_world(title: str = "", **fields) -> World:
    n = _next()
    title = title or f"World {n}"
    fields.setdefault("slug", f"world-{n}")
    # Far above the small explicit orders tests use, and unique across the run.
    fields.setdefault("order", 1000 + n)
    fields.setdefault("description", f"{title} description.")
    fields.setdefault("is_published", True)
    return World.objects.create(title=title, **fields)


def make_skill(world: World, title: str = "", **fields) -> Skill:
    n = _next()
    title = title or f"Skill {n}"
    fields.setdefault("slug", f"skill-{n}")
    fields.setdefault("order", world.skills.count() + 1)
    fields.setdefault("description", f"{title} description.")
    fields.setdefault("is_published", True)
    return Skill.objects.create(world=world, title=title, **fields)


def make_concept(skill: Skill, title: str = "", **fields) -> Concept:
    n = _next()
    title = title or f"Concept {n}"
    fields.setdefault("slug", f"concept-{n}")
    fields.setdefault("order", skill.concepts.count() + 1)
    fields.setdefault("description", f"{title} description.")
    fields.setdefault("learning_objective", f"Apply {title} in a short program.")
    fields.setdefault("is_published", True)
    return Concept.objects.create(skill=skill, title=title, **fields)


def make_lesson(concept: Concept, title: str = "", **fields) -> Lesson:
    n = _next()
    title = title or f"Lesson {n}"
    fields.setdefault("slug", f"lesson-{n}")
    fields.setdefault("order", concept.lessons.count() + 1)
    fields.setdefault("objective", f"Practise {concept.title}.")
    fields.setdefault("estimated_minutes", 8)
    fields.setdefault("is_published", True)
    return Lesson.objects.create(concept=concept, title=title, **fields)
