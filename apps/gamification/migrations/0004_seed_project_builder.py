from django.db import migrations


def seed(apps, schema_editor):
    Achievement = apps.get_model("gamification", "Achievement")
    Achievement.objects.update_or_create(
        code="project-builder",
        defaults={
            "title": "Project Builder",
            "description": "Complete your first project.",
            "icon_key": "hammer",
            "rarity": "rare",
            "order": 8,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("gamification", "0003_project_rewards")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
