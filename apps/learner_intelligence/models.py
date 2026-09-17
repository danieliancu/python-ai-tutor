"""Derived learner state. Attempts are the source of truth; these rows can always be rebuilt.

Nothing here is edited by learners or admins: ``apps.learner_intelligence.services``
recalculates every value from ``ExerciseAttempt`` history.
"""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.curriculum.models import Concept
from apps.exercises.models import LearningMode
from apps.learner_intelligence import scoring
from apps.learners.models import Enrollment


class MasteryBand(models.TextChoices):
    NOT_STARTED = scoring.MASTERY_BAND_NOT_STARTED, "Not started"
    WEAK = scoring.MASTERY_BAND_WEAK, "Weak"
    LEARNING = scoring.MASTERY_BAND_LEARNING, "Learning"
    PRACTISING = scoring.MASTERY_BAND_PRACTISING, "Practising"
    MASTERED = scoring.MASTERY_BAND_MASTERED, "Mastered"


class Trend(models.TextChoices):
    RISING = scoring.TREND_RISING, "Rising"
    STABLE = scoring.TREND_STABLE, "Stable"
    FALLING = scoring.TREND_FALLING, "Falling"
    INSUFFICIENT_DATA = scoring.TREND_INSUFFICIENT_DATA, "Insufficient data"


SCORE_VALIDATORS = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]


def _score_field(**kwargs) -> models.DecimalField:
    return models.DecimalField(
        max_digits=5, decimal_places=2, validators=SCORE_VALIDATORS, **kwargs
    )


def _score_range(field: str, name: str, nullable: bool = True) -> models.CheckConstraint:
    condition = Q(**{f"{field}__gte": 0, f"{field}__lte": 100})
    if nullable:
        condition |= Q(**{f"{field}__isnull": True})
    return models.CheckConstraint(condition=condition, name=name)


class ConceptState(models.Model):
    """One learner's current state for one Concept, within one Enrollment."""

    Band = MasteryBand
    Trend = Trend

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="concept_states"
    )
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name="learner_states")

    mastery_score = _score_field(default=Decimal("0"))
    mastery_band = models.CharField(
        max_length=16, choices=MasteryBand.choices, default=MasteryBand.NOT_STARTED
    )
    retention_score = _score_field(null=True, blank=True)
    independence_score = _score_field(null=True, blank=True)
    fluency_score = _score_field(null=True, blank=True)

    trend = models.CharField(max_length=24, choices=Trend.choices, default=Trend.INSUFFICIENT_DATA)
    trend_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-1")), MaxValueValidator(Decimal("1"))],
    )

    stability_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(scoring.MAX_REVIEW_DAYS)]
    )
    review_due_at = models.DateTimeField(null=True, blank=True)

    evidence_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    retention_evidence_count = models.PositiveIntegerField(default=0)

    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    algorithm_version = models.PositiveSmallIntegerField(default=scoring.ALGORITHM_VERSION)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["enrollment_id", "concept__skill__order", "concept__order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "concept"], name="learner_intel_state_unique_concept"
            ),
            _score_range("mastery_score", "learner_intel_state_mastery_range", nullable=False),
            _score_range("retention_score", "learner_intel_state_retention_range"),
            _score_range("independence_score", "learner_intel_state_independence_range"),
            _score_range("fluency_score", "learner_intel_state_fluency_range"),
            models.CheckConstraint(
                condition=Q(trend_score__isnull=True) | Q(trend_score__gte=-1, trend_score__lte=1),
                name="learner_intel_state_trend_score_range",
            ),
            models.CheckConstraint(
                condition=Q(mastery_band__in=MasteryBand.values),
                name="learner_intel_state_band_valid",
            ),
            models.CheckConstraint(
                condition=Q(trend__in=Trend.values), name="learner_intel_state_trend_valid"
            ),
            models.CheckConstraint(
                condition=Q(stability_days__isnull=True)
                | Q(stability_days__lte=scoring.MAX_REVIEW_DAYS),
                name="learner_intel_state_stability_range",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "review_due_at"]),
            models.Index(fields=["enrollment", "mastery_band"]),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.concept.title} · {self.mastery_score}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ConceptModeState(models.Model):
    """Performance of one learner on one Concept in one learning mode."""

    concept_state = models.ForeignKey(
        ConceptState, on_delete=models.CASCADE, related_name="mode_states"
    )
    learning_mode = models.CharField(max_length=16, choices=LearningMode.choices)
    performance_score = _score_field(default=Decimal("0"))
    attempt_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    independence_score = _score_field(null=True, blank=True)
    fluency_score = _score_field(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["concept_state_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["concept_state", "learning_mode"], name="learner_intel_mode_unique"
            ),
            models.CheckConstraint(
                condition=Q(learning_mode__in=LearningMode.values),
                name="learner_intel_mode_valid",
            ),
            _score_range(
                "performance_score", "learner_intel_mode_performance_range", nullable=False
            ),
            _score_range("independence_score", "learner_intel_mode_independence_range"),
            _score_range("fluency_score", "learner_intel_mode_fluency_range"),
        ]

    def __str__(self) -> str:
        return f"{self.concept_state} · {self.learning_mode} · {self.performance_score}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
