from collections import Counter

from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.db.models import F

from apps.curriculum.data import python_foundations as data
from apps.curriculum.models import (
    Concept,
    ConceptPrerequisite,
    Lesson,
    Skill,
    SkillPrerequisite,
    World,
)

# Seeded siblings are moved out of the way before their orders are rewritten, so a future
# reordering of the definition cannot collide with the unique (parent, order) constraint.
ORDER_PARKING_OFFSET = 10_000


def _park_orders(queryset: models.QuerySet, slugs: list[str]) -> None:
    queryset.filter(slug__in=slugs).update(order=F("order") + ORDER_PARKING_OFFSET)


class Command(BaseCommand):
    help = (
        "Create or update the Python Foundations curriculum. Safe to run repeatedly: records "
        "are matched by slug within their parent and unrelated records are left untouched."
    )

    def handle(self, *args, **options) -> None:
        self.stats: Counter[str] = Counter()
        with transaction.atomic():
            world = self._upsert(World, {"slug": data.WORLD["slug"]}, self._fields(data.WORLD))
            skills = self._seed_skills(world)
            concepts = self._seed_concepts(skills)
            self._seed_skill_prerequisites(skills)
            self._seed_concept_prerequisites(concepts)

        for label in ("world", "skill", "concept", "lesson"):
            self.stdout.write(
                f"{label.title()}s: {self.stats[f'{label}_created']} created, "
                f"{self.stats[f'{label}_updated']} updated"
            )
        for label in ("skill_edge", "concept_edge"):
            self.stdout.write(
                f"{label.replace('_', ' ').capitalize()}s: {self.stats[f'{label}_created']} "
                f"created, {self.stats[f'{label}_existing']} already present"
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded curriculum: {world.title}"))

    @staticmethod
    def _fields(definition: dict, *exclude: str) -> dict:
        return {k: v for k, v in definition.items() if k not in {"slug", *exclude}}

    def _upsert(self, model: type[models.Model], lookup: dict, defaults: dict) -> models.Model:
        obj, created = model.objects.update_or_create(
            **lookup, defaults={**defaults, "is_published": True}
        )
        label = model._meta.model_name
        self.stats[f"{label}_{'created' if created else 'updated'}"] += 1
        return obj

    def _seed_skills(self, world: World) -> dict[str, Skill]:
        _park_orders(world.skills.all(), [s["slug"] for s in data.SKILLS])
        skills = {}
        for order, definition in enumerate(data.SKILLS, start=1):
            skills[definition["slug"]] = self._upsert(
                Skill,
                {"world": world, "slug": definition["slug"]},
                {**self._fields(definition, "concepts"), "order": order},
            )
        return skills

    def _seed_concepts(self, skills: dict[str, Skill]) -> dict[str, Concept]:
        concepts = {}
        for skill_definition in data.SKILLS:
            skill = skills[skill_definition["slug"]]
            _park_orders(skill.concepts.all(), [c["slug"] for c in skill_definition["concepts"]])
            for order, definition in enumerate(skill_definition["concepts"], start=1):
                concept = self._upsert(
                    Concept,
                    {"skill": skill, "slug": definition["slug"]},
                    {**self._fields(definition, "lessons"), "order": order},
                )
                concepts[f"{skill.slug}/{concept.slug}"] = concept
                self._seed_lessons(concept, definition["lessons"])
        return concepts

    def _seed_lessons(self, concept: Concept, definitions: list[dict]) -> None:
        _park_orders(concept.lessons.all(), [d["slug"] for d in definitions])
        for order, definition in enumerate(definitions, start=1):
            self._upsert(
                Lesson,
                {"concept": concept, "slug": definition["slug"]},
                {**self._fields(definition), "order": order},
            )

    def _seed_skill_prerequisites(self, skills: dict[str, Skill]) -> None:
        for skill_slug, prerequisite_slug in data.SKILL_PREREQUISITES:
            _, created = SkillPrerequisite.objects.get_or_create(
                skill=skills[skill_slug], prerequisite=skills[prerequisite_slug]
            )
            self.stats[f"skill_edge_{'created' if created else 'existing'}"] += 1

    def _seed_concept_prerequisites(self, concepts: dict[str, Concept]) -> None:
        for concept_ref, prerequisite_ref in data.CONCEPT_PREREQUISITES:
            _, created = ConceptPrerequisite.objects.get_or_create(
                concept=concepts[concept_ref], prerequisite=concepts[prerequisite_ref]
            )
            self.stats[f"concept_edge_{'created' if created else 'existing'}"] += 1
