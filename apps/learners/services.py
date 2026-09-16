"""Explicit learner operations used by views. No signals: profiles are created on demand."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.curriculum.models import World
from apps.learners.models import Enrollment, LearnerProfile


def get_or_create_learner_profile(user: AbstractBaseUser) -> LearnerProfile:
    profile, _ = LearnerProfile.objects.get_or_create(user=user)
    return profile


def needs_onboarding(user: AbstractBaseUser) -> bool:
    """True unless the user has a profile with completed onboarding. Never creates a profile."""
    return not LearnerProfile.objects.filter(
        user=user, onboarding_completed_at__isnull=False
    ).exists()


def complete_onboarding(profile: LearnerProfile, preferred_name: str, world: World) -> Enrollment:
    """Save the learner's name, enroll them in ``world`` and mark onboarding complete.

    All-or-nothing, and safe to repeat: an existing enrollment is reused.
    """
    with transaction.atomic():
        enrollment, _ = Enrollment.objects.get_or_create(learner=profile, world=world)
        profile.preferred_name = preferred_name
        if profile.onboarding_completed_at is None:
            profile.onboarding_completed_at = timezone.now()
        profile.save()
    return enrollment
