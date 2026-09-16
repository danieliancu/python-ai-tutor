"""The Exercise: the smallest unit of curriculum content, for any subject.

``response_type`` says HOW the learner answers (code, a choice, a translation...).
``learning_mode`` says WHAT cognitive level is trained (recognise, complete, fix, create).
``content`` is safe to show learners; ``evaluation_spec`` is private configuration for the
future Evaluation Engine and must never reach learner-facing output.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.curriculum.models import Lesson
from apps.exercises.validation import validate_exercise_json


class ResponseType(models.TextChoices):
    CODE = "code", "Code"
    MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
    FILL_GAP = "fill_gap", "Fill the gap"
    TEXT = "text", "Text"
    TRANSLATION = "translation", "Translation"
    NUMERIC = "numeric", "Numeric"
    MATH_EXPRESSION = "math_expression", "Math expression"
    SPEAKING = "speaking", "Speaking"
    LISTENING = "listening", "Listening"


class LearningMode(models.TextChoices):
    RECOGNISE = "recognise", "Recognise"
    COMPLETE = "complete", "Complete"
    FIX = "fix", "Fix"
    CREATE = "create", "Create"


class Exercise(models.Model):
    ResponseType = ResponseType
    LearningMode = LearningMode

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="exercises")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    prompt = models.TextField()
    instructions = models.TextField(blank=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    response_type = models.CharField(max_length=32, choices=ResponseType.choices)
    learning_mode = models.CharField(max_length=16, choices=LearningMode.choices)
    content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Learner-facing data needed to present the exercise. Never put answers here.",
    )
    evaluation_spec = models.JSONField(
        default=dict,
        blank=True,
        help_text="Private configuration for evaluating answers. Never shown to learners.",
    )
    target_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = [
            "lesson__concept__skill__world__order",
            "lesson__concept__skill__order",
            "lesson__concept__order",
            "lesson__order",
            "order",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "slug"], name="exercises_exercise_unique_lesson_slug"
            ),
            models.UniqueConstraint(
                fields=["lesson", "order"], name="exercises_exercise_unique_lesson_order"
            ),
            models.CheckConstraint(
                condition=Q(order__gt=0),
                name="exercises_exercise_order_positive",
                violation_error_message="Order must be greater than zero.",
            ),
            models.CheckConstraint(
                condition=Q(target_seconds__isnull=True) | Q(target_seconds__gt=0),
                name="exercises_exercise_target_seconds_positive",
                violation_error_message="Target seconds must be greater than zero.",
            ),
            models.CheckConstraint(
                condition=Q(response_type__in=ResponseType.values),
                name="exercises_exercise_response_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(learning_mode__in=LearningMode.values),
                name="exercises_exercise_learning_mode_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.lesson.title}: {self.title}"

    def save(self, *args, **kwargs) -> None:
        # JSON rules can't be database constraints, so normal saves always validate.
        # bulk_create() and QuerySet.update() skip this by design.
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        # Drafts may leave the evaluation spec empty; published exercises must be checkable.
        validate_exercise_json(
            self.response_type,
            self.content,
            self.evaluation_spec,
            require_spec=self.is_published,
        )
