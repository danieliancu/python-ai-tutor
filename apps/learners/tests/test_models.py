from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import make_user
from apps.learners.models import Enrollment, LearnerProfile
from apps.learners.tests.helpers import make_world


class LearnerProfileModelTests(TestCase):
    def test_defaults_and_str(self) -> None:
        profile = LearnerProfile.objects.create(user=make_user("daniel"))
        self.assertEqual(profile.preferred_name, "")
        self.assertEqual(profile.timezone, "UTC")
        self.assertIsNone(profile.onboarding_completed_at)
        self.assertFalse(profile.has_completed_onboarding)
        self.assertIsNotNone(profile.created_at)
        self.assertEqual(str(profile), "Learner profile: daniel")

    def test_display_name_prefers_preferred_name(self) -> None:
        profile = LearnerProfile.objects.create(user=make_user("daniel"))
        self.assertEqual(profile.display_name, "daniel")
        profile.preferred_name = "Dani"
        self.assertEqual(profile.display_name, "Dani")

    def test_one_profile_per_user(self) -> None:
        user = make_user()
        profile = LearnerProfile.objects.create(user=user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LearnerProfile.objects.create(user=user)
        self.assertEqual(LearnerProfile.objects.get(), profile)
        self.assertEqual(User.objects.get(pk=user.pk).learner_profile, profile)

    def test_deleting_user_removes_profile_and_enrollments(self) -> None:
        user = make_user()
        profile = LearnerProfile.objects.create(user=user)
        Enrollment.objects.create(learner=profile, world=make_world())
        user.delete()
        self.assertFalse(LearnerProfile.objects.exists())
        self.assertFalse(Enrollment.objects.exists())


class EnrollmentModelTests(TestCase):
    def setUp(self) -> None:
        self.profile = LearnerProfile.objects.create(user=make_user("daniel"))
        self.world = make_world("Python Foundations")

    def test_defaults_and_str(self) -> None:
        enrollment = Enrollment.objects.create(learner=self.profile, world=self.world)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertIsNotNone(enrollment.enrolled_at)
        self.assertEqual(str(enrollment), "daniel → Python Foundations")

    def test_status_choices(self) -> None:
        self.assertEqual(Enrollment.Status.values, ["active", "paused", "completed"])
        enrollment = Enrollment(learner=self.profile, world=self.world, status="finished")
        with self.assertRaises(ValidationError) as ctx:
            enrollment.full_clean()
        self.assertIn("status", ctx.exception.message_dict)
        with self.assertRaises(IntegrityError), transaction.atomic():
            enrollment.save()

    def test_same_learner_and_world_cannot_repeat(self) -> None:
        Enrollment.objects.create(learner=self.profile, world=self.world)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(learner=self.profile, world=self.world)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_different_learners_can_join_the_same_world(self) -> None:
        other = LearnerProfile.objects.create(user=make_user("ana"))
        Enrollment.objects.create(learner=self.profile, world=self.world)
        Enrollment.objects.create(learner=other, world=self.world)
        self.assertEqual(self.world.enrollments.count(), 2)

    def test_one_learner_can_join_several_worlds(self) -> None:
        english = make_world("British English")
        Enrollment.objects.create(learner=self.profile, world=self.world)
        Enrollment.objects.create(learner=self.profile, world=english)
        self.assertEqual(
            list(self.profile.enrollments.values_list("world__title", flat=True)),
            ["Python Foundations", "British English"],
        )

    def test_deleting_profile_removes_its_enrollments_only(self) -> None:
        other = LearnerProfile.objects.create(user=make_user("ana"))
        Enrollment.objects.create(learner=self.profile, world=self.world)
        Enrollment.objects.create(learner=other, world=self.world)
        self.profile.delete()
        self.assertEqual(list(Enrollment.objects.values_list("learner", flat=True)), [other.pk])

    def test_enrolled_world_cannot_be_deleted(self) -> None:
        Enrollment.objects.create(learner=self.profile, world=self.world)
        with self.assertRaises(ProtectedError):
            self.world.delete()
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_enrollment_survives_unpublishing(self) -> None:
        enrollment = Enrollment.objects.create(learner=self.profile, world=self.world)
        self.world.is_published = False
        self.world.save()
        enrollment.refresh_from_db()
        enrollment.full_clean()
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
