from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests.helpers import make_user
from apps.learners.models import Enrollment, LearnerProfile
from apps.learners.services import (
    complete_onboarding,
    get_or_create_learner_profile,
    needs_onboarding,
)
from apps.learners.tests.helpers import make_world


class LearnerServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user("daniel")
        self.world = make_world()

    def test_get_or_create_is_idempotent(self) -> None:
        first = get_or_create_learner_profile(self.user)
        second = get_or_create_learner_profile(self.user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LearnerProfile.objects.count(), 1)

    def test_needs_onboarding_never_creates_a_profile(self) -> None:
        self.assertTrue(needs_onboarding(self.user))
        self.assertFalse(LearnerProfile.objects.exists())
        profile = get_or_create_learner_profile(self.user)
        self.assertTrue(needs_onboarding(self.user))
        profile.onboarding_completed_at = timezone.now()
        profile.save()
        self.assertFalse(needs_onboarding(self.user))

    def test_complete_onboarding(self) -> None:
        profile = get_or_create_learner_profile(self.user)
        enrollment = complete_onboarding(profile, "Dani", self.world)

        profile.refresh_from_db()
        self.assertEqual(profile.preferred_name, "Dani")
        self.assertIsNotNone(profile.onboarding_completed_at)
        self.assertEqual(enrollment.learner, profile)
        self.assertEqual(enrollment.world, self.world)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)

    def test_complete_onboarding_is_idempotent(self) -> None:
        profile = get_or_create_learner_profile(self.user)
        first = complete_onboarding(profile, "Dani", self.world)
        completed_at = profile.onboarding_completed_at
        second = complete_onboarding(profile, "Daniel", self.world)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Enrollment.objects.count(), 1)
        profile.refresh_from_db()
        self.assertEqual(profile.onboarding_completed_at, completed_at)
        self.assertEqual(profile.preferred_name, "Daniel")

    def test_complete_onboarding_is_all_or_nothing(self) -> None:
        profile = get_or_create_learner_profile(self.user)
        with (
            mock.patch.object(LearnerProfile, "save", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            complete_onboarding(profile, "Dani", self.world)

        self.assertFalse(Enrollment.objects.exists())
        profile.refresh_from_db()
        self.assertIsNone(profile.onboarding_completed_at)
