"""Learner attempt history: what was submitted, how it was judged, and which mistakes showed.

Stored data is a safe snapshot. The learner's own answer is kept; answers, tests and
evaluation specs of the exercise never are.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.attempts.mistakes import is_safe_details
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment

MAX_HINT_LEVEL = 10
MAX_DURATION_SECONDS = 86_400


class AttemptStatus(models.TextChoices):
    CORRECT = "correct", "Correct"
    INCORRECT = "incorrect", "Incorrect"
    INVALID = "invalid", "Invalid"
    REVIEW_REQUIRED = "review_required", "Review required"
    UNSUPPORTED = "unsupported", "Unsupported"
    UNAVAILABLE = "unavailable", "Unavailable"


class ExerciseAttempt(models.Model):
    """One learner submission for one exercise."""

    Status = AttemptStatus

    # PROTECT: attempt history is valuable and shouldn't disappear with its parents.
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="attempts")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="attempts")
    attempt_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    submitted_answer = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=AttemptStatus.choices)
    score = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    is_correct = models.BooleanField(null=True, blank=True)
    evaluator = models.CharField(max_length=64)
    message = models.CharField(max_length=300)
    diagnostics = models.JSONField(default=dict, blank=True)
    hint_level = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(MAX_HINT_LEVEL)]
    )
    used_explanation = models.BooleanField(default=False)
    used_solution = models.BooleanField(default=False)
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(MAX_DURATION_SECONDS)]
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "exercise", "attempt_number"],
                name="attempts_attempt_unique_number",
            ),
            models.CheckConstraint(
                condition=Q(attempt_number__gt=0), name="attempts_attempt_number_positive"
            ),
            models.CheckConstraint(
                condition=Q(status__in=AttemptStatus.values), name="attempts_attempt_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=0, score__lte=1),
                name="attempts_attempt_score_range",
            ),
            models.CheckConstraint(
                condition=Q(hint_level__lte=MAX_HINT_LEVEL),
                name="attempts_attempt_hint_level_range",
            ),
            models.CheckConstraint(
                condition=Q(duration_seconds__isnull=True)
                | Q(duration_seconds__lte=MAX_DURATION_SECONDS),
                name="attempts_attempt_duration_range",
            ),
        ]
        indexes = [models.Index(fields=["enrollment", "exercise", "-submitted_at"])]

    def __str__(self) -> str:
        return (
            f"{self.enrollment.learner.user.get_username()} · {self.exercise.title} "
            f"· #{self.attempt_number}"
        )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not is_safe_details(self.diagnostics):
            raise ValidationError({"diagnostics": "Diagnostics may only hold safe reason codes."})


class AttemptMistake(models.Model):
    """A mistake signal extracted from an attempt, e.g. ``output_mismatch``."""

    attempt = models.ForeignKey(ExerciseAttempt, on_delete=models.CASCADE, related_name="mistakes")
    code = models.SlugField(max_length=64)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "code"], name="attempts_mistake_unique_code"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} (attempt {self.attempt_id})"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not is_safe_details(self.details):
            raise ValidationError({"details": "Details may only hold safe codes."})
