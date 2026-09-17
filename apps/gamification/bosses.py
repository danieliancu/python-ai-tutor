"""Boss Challenge definitions: existing checkpoint exercises, marked for a bonus.

Being a boss never changes availability: the exercise is reached through the normal curriculum,
prerequisites and Next Best Action.
"""

from apps.exercises.models import Exercise
from apps.gamification.models import BossChallenge

BOSS_BONUS_XP = 100

# Python Foundations: CREATE code exercises that combine what the learner has built up so far.
PYTHON_BOSSES = (
    ("ticket-price", 1),
    ("years-to-double", 2),
    ("bank-account", 3),
    ("full-class-report", 4),
)


def sync_bosses(world_slug: str, definitions=PYTHON_BOSSES) -> dict:
    """Create or update the boss markers for a World's exercises. Safe to run repeatedly."""
    exercises = {
        exercise.slug: exercise
        for exercise in Exercise.objects.filter(
            lesson__concept__skill__world__slug=world_slug,
            slug__in=[slug for slug, _ in definitions],
        )
    }
    stats = {"created": 0, "updated": 0, "missing": []}
    for slug, order in definitions:
        exercise = exercises.get(slug)
        if exercise is None:
            stats["missing"].append(slug)
            continue
        _, created = BossChallenge.objects.update_or_create(
            exercise=exercise,
            defaults={"order": order, "bonus_xp": BOSS_BONUS_XP, "is_active": True},
        )
        stats["created" if created else "updated"] += 1
    return stats


def boss_exercise_ids(world_id: int) -> list[int]:
    return list(
        BossChallenge.objects.filter(
            is_active=True, exercise__lesson__concept__skill__world_id=world_id
        )
        .order_by("order", "id")
        .values_list("exercise_id", flat=True)
    )
