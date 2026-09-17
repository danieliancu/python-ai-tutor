from django.db import migrations

# Frozen copy of the initial catalogue (apps/gamification/achievements.py at Phase 9).
ACHIEVEMENTS = (
    ("first-step", "First Step", "Complete your first exercise correctly.", "footsteps",
     "common", 1),
    ("independent-thinker", "Independent Thinker",
     "Complete an exercise correctly without hints, explanations or solutions.", "lightbulb",
     "uncommon", 2),
    ("on-a-roll", "On a Roll", "Learn on 3 days in a row.", "flame", "common", 3),
    ("consistent-learner", "Consistent Learner", "Learn on 7 days in a row.", "calendar",
     "rare", 4),
    ("skill-mastered", "Skill Mastered", "Master every concept in a skill.", "star", "rare", 5),
    ("boss-cleared", "Boss Cleared", "Complete your first Boss Challenge.", "trophy", "epic", 6),
    ("ten-down", "Ten Down", "Complete 10 different exercises correctly.", "target",
     "uncommon", 7),
)  # fmt: skip


def seed(apps, schema_editor):
    Achievement = apps.get_model("gamification", "Achievement")
    for code, title, description, icon_key, rarity, order in ACHIEVEMENTS:
        Achievement.objects.update_or_create(
            code=code,
            defaults={
                "title": title,
                "description": description,
                "icon_key": icon_key,
                "rarity": rarity,
                "order": order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("gamification", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
