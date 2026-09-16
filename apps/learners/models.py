"""Learner identity and curriculum enrollment.

User (authentication) → LearnerProfile (learner identity and preferences) → Enrollment → World.
Nothing here is specific to one subject: a learner can be enrolled in any number of Worlds.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.curriculum.models import World


class LearnerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learner_profile"
    )
    preferred_name = models.CharField(max_length=80, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"Learner profile: {self.user.get_username()}"

    @property
    def display_name(self) -> str:
        return self.preferred_name or self.user.get_username()

    @property
    def has_completed_onboarding(self) -> bool:
        return self.onboarding_completed_at is not None


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"


class Enrollment(models.Model):
    """A learner enrolled in a World.

    Deleting an enrolled World is blocked (PROTECT): unpublish it instead so enrollment
    history survives. Whether a World may be newly joined is decided by onboarding, not here.
    """

    Status = EnrollmentStatus

    learner = models.ForeignKey(
        LearnerProfile, on_delete=models.CASCADE, related_name="enrollments"
    )
    world = models.ForeignKey(World, on_delete=models.PROTECT, related_name="enrollments")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["enrolled_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "world"],
                name="learners_enrollment_unique_learner_world",
                violation_error_message="This learner is already enrolled in this World.",
            ),
            models.CheckConstraint(
                condition=Q(status__in=EnrollmentStatus.values),
                name="learners_enrollment_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.learner.user.get_username()} → {self.world.title}"
