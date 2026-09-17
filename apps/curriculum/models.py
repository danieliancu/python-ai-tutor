"""Curriculum domain: World → Skill → Concept → Lesson, plus prerequisite graphs.

Prerequisite edges are validated in ``clean()`` (self-dependency, same World, no cycles) and
every normal ``save()`` runs ``full_clean()``, so invalid edges cannot enter through ordinary
ORM usage. ``bulk_create()`` and ``QuerySet.update()`` skip ``save()`` by design; the database
still enforces edge uniqueness and the no-self-dependency check.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


def _order_field() -> models.PositiveSmallIntegerField:
    return models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])


def _positive_order(name: str) -> models.CheckConstraint:
    return models.CheckConstraint(
        condition=Q(order__gt=0),
        name=name,
        violation_error_message="Order must be greater than zero.",
    )


def _find_requirement_path(
    edge_model: type[models.Model],
    node_field: str,
    start_id: int,
    target_id: int,
    exclude_pk: int | None,
) -> list[int] | None:
    """Return node ids from ``start_id`` to ``target_id`` along existing "requires" edges.

    Breadth-first, one query per depth level, visiting edges in id order so the reported path
    is deterministic. ``exclude_pk`` ignores the edge being edited.
    """
    parents: dict[int, int | None] = {start_id: None}
    frontier = [start_id]
    while frontier:
        edges = edge_model.objects.filter(**{f"{node_field}_id__in": frontier})
        if exclude_pk is not None:
            edges = edges.exclude(pk=exclude_pk)
        rows = edges.values_list(f"{node_field}_id", "prerequisite_id").order_by(
            f"{node_field}_id", "prerequisite_id"
        )
        next_frontier = []
        for node_id, prerequisite_id in rows:
            if prerequisite_id in parents:
                continue
            parents[prerequisite_id] = node_id
            if prerequisite_id == target_id:
                path = [prerequisite_id]
                while parents[path[-1]] is not None:
                    path.append(parents[path[-1]])
                return path[::-1]
            next_frontier.append(prerequisite_id)
        frontier = next_frontier
    return None


def _validate_edge(edge: models.Model, node_field: str, node_label: str) -> None:
    """Shared prerequisite rules. Cross-World checks live on each edge model."""
    node_id = getattr(edge, f"{node_field}_id")
    prerequisite_id = edge.prerequisite_id
    if node_id is None or prerequisite_id is None:
        return
    if node_id == prerequisite_id:
        raise ValidationError({"prerequisite": f"A {node_label} cannot require itself."})

    edge.validate_same_world()

    path = _find_requirement_path(type(edge), node_field, prerequisite_id, node_id, edge.pk)
    if path is not None:
        node_model = edge._meta.get_field(node_field).related_model
        titles = node_model.objects.in_bulk([node_id, *path])
        chain = " → ".join(titles[pk].title for pk in [node_id, *path])
        raise ValidationError({"prerequisite": f"This prerequisite would create a cycle: {chain}."})


class World(models.Model):
    """A top-level learning path, e.g. Python Foundations."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    # The subject area (e.g. "python", "english"). Free text so new domains need no migration;
    # it selects domain-specific behaviour such as the tutor adapter.
    domain = models.SlugField(max_length=50, default="general", db_index=True)
    order = _order_field()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["slug"], name="curriculum_world_unique_slug"),
            models.UniqueConstraint(fields=["order"], name="curriculum_world_unique_order"),
            _positive_order("curriculum_world_order_positive"),
        ]

    def __str__(self) -> str:
        return self.title


class Skill(models.Model):
    """A major learning section inside a World, e.g. Loops."""

    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name="skills")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    order = _order_field()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["world_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["world", "slug"], name="curriculum_skill_unique_world_slug"
            ),
            models.UniqueConstraint(
                fields=["world", "order"], name="curriculum_skill_unique_world_order"
            ),
            _positive_order("curriculum_skill_order_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.world.title} › {self.title}"


class SkillPrerequisite(models.Model):
    """``skill`` requires ``prerequisite`` (both in the same World)."""

    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="prerequisite_links")
    prerequisite = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="required_by_links"
    )

    class Meta:
        ordering = ["skill_id", "prerequisite_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "prerequisite"], name="curriculum_skillprerequisite_unique_edge"
            ),
            models.CheckConstraint(
                condition=~Q(skill=F("prerequisite")),
                name="curriculum_skillprerequisite_not_self",
                violation_error_message="A skill cannot require itself.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.skill.title} requires {self.prerequisite.title}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        _validate_edge(self, "skill", "skill")

    def validate_same_world(self) -> None:
        if self.skill.world_id != self.prerequisite.world_id:
            raise ValidationError(
                {"prerequisite": "A prerequisite skill must belong to the same World."}
            )


class Concept(models.Model):
    """A measurable unit of understanding inside a Skill, e.g. range()."""

    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="concepts")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    learning_objective = models.TextField(
        help_text="What the learner should be able to do after mastering this concept."
    )
    order = _order_field()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["skill_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "slug"], name="curriculum_concept_unique_skill_slug"
            ),
            models.UniqueConstraint(
                fields=["skill", "order"], name="curriculum_concept_unique_skill_order"
            ),
            _positive_order("curriculum_concept_order_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.skill.title}: {self.title}"


class ConceptPrerequisite(models.Model):
    """``concept`` requires ``prerequisite``; Skills may differ, the World may not."""

    concept = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="prerequisite_links"
    )
    prerequisite = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="required_by_links"
    )

    class Meta:
        ordering = ["concept_id", "prerequisite_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["concept", "prerequisite"],
                name="curriculum_conceptprerequisite_unique_edge",
            ),
            models.CheckConstraint(
                condition=~Q(concept=F("prerequisite")),
                name="curriculum_conceptprerequisite_not_self",
                violation_error_message="A concept cannot require itself.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.concept.title} requires {self.prerequisite.title}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        _validate_edge(self, "concept", "concept")

    def validate_same_world(self) -> None:
        worlds = dict(
            Concept.objects.filter(pk__in=[self.concept_id, self.prerequisite_id]).values_list(
                "pk", "skill__world_id"
            )
        )
        if worlds.get(self.concept_id) != worlds.get(self.prerequisite_id):
            raise ValidationError(
                {"prerequisite": "A prerequisite concept must belong to the same World."}
            )


class Lesson(models.Model):
    """A unit of teaching attached to one primary Concept."""

    class Kind(models.TextChoices):
        LEARN = "learn", "Learn"
        PRACTICE = "practice", "Practice"
        REVIEW = "review", "Review"
        CHALLENGE = "challenge", "Challenge"

    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    objective = models.TextField()
    summary = models.TextField(blank=True)
    order = _order_field()
    estimated_minutes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.LEARN)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["concept_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["concept", "slug"], name="curriculum_lesson_unique_concept_slug"
            ),
            models.UniqueConstraint(
                fields=["concept", "order"], name="curriculum_lesson_unique_concept_order"
            ),
            _positive_order("curriculum_lesson_order_positive"),
            models.CheckConstraint(
                condition=Q(estimated_minutes__gt=0),
                name="curriculum_lesson_estimated_minutes_positive",
                violation_error_message="Estimated minutes must be greater than zero.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.concept.title}: {self.title}"
