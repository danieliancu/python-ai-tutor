"""Projects: larger, staged applications that combine several concepts of one World.

Project → ProjectStage (ordered). A learner's work lives in one ProjectDraft per enrollment
and project; each check of a stage is a ProjectSubmission; finishing every stage creates a
ProjectCompletion. Projects read learner state to decide availability but never change it.
Nothing here is Python-specific: evaluation is chosen by ``World.domain``.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.attempts.models import MAX_DURATION_SECONDS, AttemptStatus
from apps.curriculum.models import Concept, World
from apps.learners.models import Enrollment
from apps.projects.evaluation.spec import stage_spec_errors

DEFAULT_MINIMUM_MASTERY = 65
DEFAULT_PROJECT_XP = 150


class Difficulty(models.TextChoices):
    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class Project(models.Model):
    world = models.ForeignKey(World, on_delete=models.PROTECT, related_name="projects")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    summary = models.CharField(max_length=300)
    brief = models.TextField()
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    difficulty = models.CharField(
        max_length=16, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    estimated_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    xp_reward = models.PositiveIntegerField(
        default=DEFAULT_PROJECT_XP, validators=[MinValueValidator(1)]
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["world__order", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["world", "slug"], name="projects_project_unique_slug"),
            models.UniqueConstraint(
                fields=["world", "order"], name="projects_project_unique_order"
            ),
            models.CheckConstraint(condition=Q(order__gt=0), name="projects_project_order_pos"),
            models.CheckConstraint(
                condition=Q(xp_reward__gt=0), name="projects_project_xp_positive"
            ),
            models.CheckConstraint(
                condition=Q(estimated_minutes__gt=0), name="projects_project_minutes_positive"
            ),
            models.CheckConstraint(
                condition=Q(difficulty__in=Difficulty.values),
                name="projects_project_difficulty_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.world.title}: {self.title}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectConceptRequirement(models.Model):
    """A concept the learner must have learned (to ``minimum_mastery``) before the project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="requirements")
    concept = models.ForeignKey(
        Concept, on_delete=models.PROTECT, related_name="project_requirements"
    )
    minimum_mastery = models.PositiveSmallIntegerField(
        default=DEFAULT_MINIMUM_MASTERY,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ["concept__skill__order", "concept__order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "concept"], name="projects_requirement_unique_concept"
            ),
            models.CheckConstraint(
                condition=Q(minimum_mastery__gte=0, minimum_mastery__lte=100),
                name="projects_requirement_mastery_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.concept.title} ≥ {self.minimum_mastery}%"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if (
            self.project_id
            and self.concept_id
            and self.concept.skill.world_id != self.project.world_id
        ):
            raise ValidationError(
                {"concept": "The concept must belong to the same World as the project."}
            )


class ProjectStage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stages")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    objective = models.CharField(max_length=300)
    instructions = models.TextField()
    # Public checklist shown to learners (and to the project coach).
    requirements = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    estimated_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    starter_code = models.TextField(blank=True)
    # PRIVATE: tests, drivers and fixture files. Never sent to learners or to the AI.
    evaluation_spec = models.JSONField(default=dict, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["project_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "slug"], name="projects_stage_unique_slug"),
            models.UniqueConstraint(
                fields=["project", "order"], name="projects_stage_unique_order"
            ),
            models.CheckConstraint(condition=Q(order__gt=0), name="projects_stage_order_pos"),
        ]

    def __str__(self) -> str:
        return f"{self.project.title} · {self.order}. {self.title}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        errors = {}
        if not isinstance(self.requirements, list) or not all(
            isinstance(item, str) and item.strip() for item in self.requirements
        ):
            errors["requirements"] = "Requirements must be a list of non-empty texts."
        if self.is_published or self.evaluation_spec:
            problems = stage_spec_errors(self.evaluation_spec)
            if problems:
                errors["evaluation_spec"] = problems
        if errors:
            raise ValidationError(errors)


class ProjectDraft(models.Model):
    """The learner's current project source, kept between visits and stages."""

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="project_drafts"
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="drafts")
    source_code = models.TextField(blank=True)
    current_stage = models.ForeignKey(
        ProjectStage, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "project"], name="projects_draft_unique_project"
            ),
        ]

    def __str__(self) -> str:
        return f"Draft: {self.project.title} ({self.enrollment})"


# Project stages are judged like code exercises; "review required" never applies.
SUBMISSION_STATUSES = (
    AttemptStatus.CORRECT,
    AttemptStatus.INCORRECT,
    AttemptStatus.INVALID,
    AttemptStatus.UNSUPPORTED,
    AttemptStatus.UNAVAILABLE,
)


class ProjectSubmission(models.Model):
    """One check of one stage. Only safe snapshots are stored (never tests or expectations)."""

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.PROTECT, related_name="project_submissions"
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="submissions")
    stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, related_name="submissions")
    attempt_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    submitted_source = models.TextField()
    status = models.CharField(
        max_length=32, choices=[(s.value, s.label) for s in SUBMISSION_STATUSES]
    )
    score = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    is_correct = models.BooleanField(null=True, blank=True)
    evaluator = models.CharField(max_length=64)
    message = models.CharField(max_length=300)
    diagnostics = models.JSONField(default=dict, blank=True)
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(MAX_DURATION_SECONDS)]
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "stage", "attempt_number"],
                name="projects_submission_unique_number",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[s.value for s in SUBMISSION_STATUSES]),
                name="projects_submission_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=0, score__lte=1),
                name="projects_submission_score_range",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "project", "stage"]),
            models.Index(fields=["enrollment", "submitted_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.stage} #{self.attempt_number}: {self.status}"


class ProjectCompletion(models.Model):
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="project_completions"
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="completions")
    final_submission = models.ForeignKey(
        ProjectSubmission, on_delete=models.PROTECT, related_name="+"
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completed_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "project"], name="projects_completion_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project.title} completed ({self.enrollment})"
