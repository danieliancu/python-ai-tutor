from collections import Counter

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from apps.curriculum.models import Concept, World
from apps.projects.data.python_foundations import PROJECTS, WORLD_SLUG
from apps.projects.models import Project, ProjectConceptRequirement, ProjectStage

# Seeded rows are moved out of the way before orders are rewritten, so reordering can't
# collide with the unique order constraints.
ORDER_PARKING_OFFSET = 10_000
PROJECT_FIELDS = ("title", "summary", "brief", "difficulty", "estimated_minutes", "xp_reward")
STAGE_FIELDS = (
    "title",
    "objective",
    "instructions",
    "requirements",
    "estimated_minutes",
    "starter_code",
    "evaluation_spec",
)


class Command(BaseCommand):
    help = (
        "Create or update the Python Foundations projects. Requires the curriculum from "
        "seed_curriculum. Safe to run repeatedly; projects it does not define are untouched."
    )

    def handle(self, *args, **options) -> None:
        world = World.objects.filter(slug=WORLD_SLUG).first()
        if world is None:
            raise CommandError(
                f"The '{WORLD_SLUG}' curriculum does not exist yet. "
                "Run `python manage.py seed_curriculum` first."
            )
        concepts = self._concepts(world)
        missing = sorted(
            {path for project in PROJECTS for path in project["requirements"]} - set(concepts)
        )
        if missing:
            raise CommandError(
                "These concepts are missing from the curriculum: "
                + ", ".join(missing)
                + ". Run `python manage.py seed_curriculum` to update it."
            )

        stats = Counter()
        try:
            with transaction.atomic():
                Project.objects.filter(world=world, slug__in=[p["slug"] for p in PROJECTS]).update(
                    order=F("order") + ORDER_PARKING_OFFSET
                )
                for definition in PROJECTS:
                    created = self._upsert(world, definition, concepts, stats)
                    stats["projects created" if created else "projects updated"] += 1
        except ValidationError as exc:
            raise CommandError(f"Invalid project content: {exc}") from exc

        total = Project.objects.filter(world=world).count()
        self.stdout.write(
            f"Projects: {stats['projects created']} created, {stats['projects updated']} "
            f"updated; {stats['stages']} stages, {stats['requirements']} requirements"
        )
        self.stdout.write(self.style.SUCCESS(f"Python Foundations now has {total} projects."))

    @staticmethod
    def _concepts(world: World) -> dict[str, Concept]:
        return {
            f"{concept.skill.slug}/{concept.slug}": concept
            for concept in Concept.objects.filter(skill__world=world).select_related("skill")
        }

    @staticmethod
    def _upsert(world, definition, concepts, stats) -> bool:
        project = Project.objects.filter(world=world, slug=definition["slug"]).first()
        created = project is None
        if created:
            project = Project(world=world, slug=definition["slug"])
        for field in PROJECT_FIELDS:
            setattr(project, field, definition[field])
        project.order = definition["order"]
        project.is_published = True
        project.save()

        wanted = [concepts[path] for path in definition["requirements"]]
        project.requirements.exclude(concept__in=wanted).delete()
        for concept in wanted:
            ProjectConceptRequirement.objects.update_or_create(project=project, concept=concept)
            stats["requirements"] += 1

        slugs = [stage["slug"] for stage in definition["stages"]]
        # Stages the definition no longer has are unpublished (their history is kept).
        project.stages.exclude(slug__in=slugs).update(is_published=False)
        project.stages.update(order=F("order") + ORDER_PARKING_OFFSET)
        for order, stage_definition in enumerate(definition["stages"], start=1):
            stage = ProjectStage.objects.filter(
                project=project, slug=stage_definition["slug"]
            ).first() or ProjectStage(project=project, slug=stage_definition["slug"])
            for field in STAGE_FIELDS:
                setattr(stage, field, stage_definition[field])
            stage.order = order
            stage.is_published = True
            stage.save()
            stats["stages"] += 1
        return created
