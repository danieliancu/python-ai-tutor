"""Derived misconception data. Attempts and exercise metadata are the source of truth.

``AttemptMistake`` records what went wrong in one submission. ``MisconceptionState`` is a
pedagogical pattern inferred from repeated evidence. Both tables here are rebuilt by
``apps.misconceptions.services`` and never edited by hand.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.attempts.models import ExerciseAttempt
from apps.curriculum.models import Concept
from apps.learners.models import Enrollment
from apps.misconceptions import evidence, scoring
from apps.misconceptions.definitions import is_safe_code


class EvidenceKind(models.TextChoices):
    POSITIVE = evidence.POSITIVE, "Supports"
    COUNTER = evidence.COUNTER, "Counters"


class MisconceptionStatus(models.TextChoices):
    WATCH = scoring.WATCH, "Watch"
    ACTIVE = scoring.ACTIVE, "Active"
    RESOLVED = scoring.RESOLVED, "Resolved"


def _validate_code(value: str) -> None:
    if not is_safe_code(value):
        raise ValidationError("Use a lowercase code such as “off-by-one”.")


class MisconceptionEvidence(models.Model):
    """What one attempt says for (or against) one misconception, from one detector."""

    Kind = EvidenceKind

    attempt = models.ForeignKey(
        ExerciseAttempt, on_delete=models.CASCADE, related_name="misconception_evidence"
    )
    code = models.CharField(max_length=64, validators=[_validate_code])
    kind = models.CharField(max_length=16, choices=EvidenceKind.choices)
    strength = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    source = models.CharField(max_length=64, validators=[_validate_code])
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["attempt_id", "code", "kind", "source"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "code", "kind", "source"],
                name="misconceptions_evidence_unique_signal",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=EvidenceKind.values), name="misconceptions_evidence_kind"
            ),
            models.CheckConstraint(
                condition=Q(strength__gte=0, strength__lte=1),
                name="misconceptions_evidence_strength_range",
            ),
        ]
        indexes = [models.Index(fields=["code", "kind"], name="misconc_evidence_code_kind")]
        verbose_name_plural = "misconception evidence"

    def __str__(self) -> str:
        return f"{self.code} · {self.kind} · {self.strength} (attempt {self.attempt_id})"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not evidence.is_safe_details(self.details):
            raise ValidationError({"details": "Details may only hold safe codes."})


class MisconceptionState(models.Model):
    """Current derived belief about one misconception, per enrollment and concept."""

    Status = MisconceptionStatus

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="misconception_states"
    )
    concept = models.ForeignKey(
        Concept, on_delete=models.CASCADE, related_name="misconception_states"
    )
    code = models.CharField(max_length=64, validators=[_validate_code])

    status = models.CharField(max_length=16, choices=MisconceptionStatus.choices)
    # Deterministic evidence strength (0–100) for product logic, not a probability.
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )

    positive_evidence_count = models.PositiveIntegerField(default=0)
    counter_evidence_count = models.PositiveIntegerField(default=0)
    strong_evidence_count = models.PositiveIntegerField(default=0)
    distinct_exercise_count = models.PositiveIntegerField(default=0)

    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    last_confirmed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    algorithm_version = models.PositiveSmallIntegerField(
        default=scoring.MISCONCEPTION_ALGORITHM_VERSION
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["enrollment_id", "concept_id", "-confidence_score", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "concept", "code"],
                name="misconceptions_state_unique_code",
            ),
            models.CheckConstraint(
                condition=Q(status__in=MisconceptionStatus.values),
                name="misconceptions_state_status",
            ),
            models.CheckConstraint(
                condition=Q(confidence_score__gte=0, confidence_score__lte=100),
                name="misconceptions_state_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "status"], name="misconc_state_status"),
            models.Index(fields=["enrollment", "code"], name="misconc_state_code"),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.code} · {self.status} ({self.confidence_score})"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
