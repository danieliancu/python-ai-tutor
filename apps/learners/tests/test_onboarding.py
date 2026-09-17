from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.helpers import make_user
from apps.curriculum.models import World
from apps.learners.models import Enrollment, LearnerProfile
from apps.learners.tests.helpers import make_world

URL = reverse("learners:onboarding")


class OnboardingTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user("daniel")
        self.client.force_login(self.user)
        self.python = make_world(
            "Python Foundations", description="Write real Python programs.", order=1
        )
        self.english = make_world("British English", order=2)
        self.draft = make_world("Secret Draft World", is_published=False, order=3)

    def post(self, **data):
        payload = {"preferred_name": "Dani", "world": self.python.pk}
        payload.update(data)
        return self.client.post(URL, payload)

    def profile(self) -> LearnerProfile:
        return LearnerProfile.objects.get(user=self.user)

    def test_requires_login(self) -> None:
        self.client.logout()
        response = self.client.get(URL)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={URL}")

    def test_page_offers_only_published_worlds_from_the_database(self) -> None:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, daniel")
        self.assertContains(response, "Python Foundations")
        self.assertContains(response, "Write real Python programs.")
        self.assertContains(response, "British English")
        self.assertNotContains(response, "Secret Draft World")
        self.assertContains(response, 'type="radio"', count=2)
        self.assertContains(response, 'autocomplete="name"')
        # Entering onboarding creates the learner profile.
        self.assertTrue(LearnerProfile.objects.filter(user=self.user).exists())

    def test_single_world_is_preselected(self) -> None:
        World.objects.exclude(pk=self.python.pk).update(is_published=False)
        response = self.client.get(URL)
        self.assertContains(response, "checked", count=1)

    def test_successful_onboarding(self) -> None:
        response = self.post(world=self.english.pk)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        profile = self.profile()
        self.assertEqual(profile.preferred_name, "Dani")
        self.assertIsNotNone(profile.onboarding_completed_at)
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.learner, enrollment.world), (profile, self.english))

    def test_repeated_post_does_not_duplicate_enrollment(self) -> None:
        self.post()
        response = self.post(preferred_name="Someone else")
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(self.profile().preferred_name, "Dani")

    def test_completed_learner_is_sent_home(self) -> None:
        LearnerProfile.objects.create(user=self.user, onboarding_completed_at=timezone.now())
        self.assertRedirects(self.client.get(URL), reverse("home"), fetch_redirect_response=False)

    def assert_nothing_completed(self) -> None:
        self.assertFalse(Enrollment.objects.exists())
        self.assertIsNone(self.profile().onboarding_completed_at)

    def test_crafted_post_for_unpublished_world_is_rejected(self) -> None:
        response = self.post(world=self.draft.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose one of the available learning paths.")
        self.assert_nothing_completed()

    def test_missing_or_bogus_world_is_rejected(self) -> None:
        for value in ("", "999999", "not-a-number"):
            with self.subTest(world=value):
                response = self.post(world=value)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors["world"])
        self.assert_nothing_completed()

    def test_blank_preferred_name_is_rejected(self) -> None:
        response = self.post(preferred_name="   ")
        self.assertEqual(response.status_code, 200)
        self.assertIn("preferred_name", response.context["form"].errors)
        self.assertContains(response, 'aria-invalid="true"')
        self.assert_nothing_completed()

    def test_no_published_worlds_shows_a_friendly_state(self) -> None:
        World.objects.update(is_published=False)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No learning paths are currently available.")
        self.assertNotContains(response, "Start learning")

        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No learning paths are currently available.")
        self.assert_nothing_completed()

    def test_other_http_methods_are_rejected(self) -> None:
        self.assertEqual(self.client.put(URL).status_code, 405)
