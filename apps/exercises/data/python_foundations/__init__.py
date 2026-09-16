"""Python Foundations exercise pack, applied by ``manage.py seed_python_exercises``.

Each skill module maps (concept slug, lesson slug) to an ordered list of exercises; the list
position is the exercise's order within its lesson (easiest first). Identity is
lesson + exercise slug, so re-running the seed updates exercises instead of duplicating them.
"""

from apps.exercises.data.python_foundations import (
    data_collections,
    debugging,
    decisions,
    functions,
    loops,
    oop_basics,
    python_developer,
    python_structure,
    real_data,
    start,
    variables,
)

WORLD_SLUG = "python-foundations"

SKILL_MODULES = (
    start,
    variables,
    decisions,
    data_collections,
    loops,
    functions,
    debugging,
    python_structure,
    oop_basics,
    real_data,
    python_developer,
)


def _flatten() -> list[dict]:
    exercises = []
    for module in SKILL_MODULES:
        for (concept, lesson), items in module.LESSONS.items():
            for order, exercise in enumerate(items, start=1):
                exercises.append(
                    {
                        "skill": module.SKILL,
                        "concept": concept,
                        "lesson": lesson,
                        "order": order,
                        **exercise,
                    }
                )
    return exercises


EXERCISES = _flatten()
