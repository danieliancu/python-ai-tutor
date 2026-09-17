from collections import Counter, defaultdict

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from apps.curriculum.models import Lesson, World
from apps.exercises.data.python_foundations import EXERCISES, WORLD_SLUG
from apps.exercises.models import Exercise

# Seeded exercises are moved out of the way before their orders are rewritten, so reordering
# a lesson's definition can't collide with the unique (lesson, order) constraint.
ORDER_PARKING_OFFSET = 10_000

SEEDED_FIELDS = (
    "title",
    "prompt",
    "instructions",
    "order",
    "response_type",
    "learning_mode",
    "content",
    "evaluation_spec",
    "target_seconds",
)


class Command(BaseCommand):
    help = (
        "Create or update the Python Foundations exercise pack. Requires the curriculum from "
        "seed_curriculum. Safe to run repeatedly; exercises it does not define are untouched."
    )

    def handle(self, *args, **options) -> None:
        if not World.objects.filter(slug=WORLD_SLUG).exists():
            raise CommandError(
                f"The '{WORLD_SLUG}' curriculum does not exist yet. "
                "Run `python manage.py seed_curriculum` first."
            )
        lessons = self._lessons_by_path()
        by_lesson = defaultdict(list)
        missing = set()
        for definition in EXERCISES:
            path = (definition["skill"], definition["concept"], definition["lesson"])
            if path in lessons:
                by_lesson[lessons[path]].append(definition)
            else:
                missing.add("/".join(path))
        if missing:
            raise CommandError(
                "These lessons are missing from the curriculum: "
                + ", ".join(sorted(missing))
                + ". Run `python manage.py seed_curriculum` to update it."
            )

        stats = Counter()
        with transaction.atomic():
            for lesson, definitions in by_lesson.items():
                lesson.exercises.filter(slug__in=[d["slug"] for d in definitions]).update(
                    order=F("order") + ORDER_PARKING_OFFSET
                )
                for definition in definitions:
                    created = self._upsert(lesson, definition)
                    stats["created" if created else "updated"] += 1

        total = Exercise.objects.filter(lesson__concept__skill__world__slug=WORLD_SLUG).count()
        self.stdout.write(
            f"Exercises: {stats['created']} created, {stats['updated']} updated "
            f"({len(by_lesson)} lessons)"
        )
        # Mark the checkpoint exercises as Boss Challenges (imported lazily: gamification
        # builds on exercises, not the other way round).
        from apps.gamification.bosses import sync_bosses

        bosses = sync_bosses(WORLD_SLUG)
        self.stdout.write(
            f"Boss Challenges: {bosses['created']} created, {bosses['updated']} updated"
            + (f" (missing: {', '.join(bosses['missing'])})" if bosses["missing"] else "")
        )
        self.stdout.write(self.style.SUCCESS(f"Python Foundations now has {total} exercises."))

    @staticmethod
    def _lessons_by_path() -> dict[tuple[str, str, str], Lesson]:
        lessons = Lesson.objects.filter(concept__skill__world__slug=WORLD_SLUG).select_related(
            "concept__skill"
        )
        return {
            (lesson.concept.skill.slug, lesson.concept.slug, lesson.slug): lesson
            for lesson in lessons
        }

    @staticmethod
    def _upsert(lesson: Lesson, definition: dict) -> bool:
        defaults = {field: definition[field] for field in SEEDED_FIELDS}
        defaults["is_published"] = True
        try:
            _, created = Exercise.objects.update_or_create(
                lesson=lesson, slug=definition["slug"], defaults=defaults
            )
        except ValidationError as exc:
            path = f"{definition['skill']}/{definition['concept']}/{definition['lesson']}"
            raise CommandError(f"Invalid exercise {path}/{definition['slug']}: {exc}") from exc
        return created
