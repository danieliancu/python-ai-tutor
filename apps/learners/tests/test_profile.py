from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from apps.accounts.tests.helpers import make_user
from apps.learners.models import Enrollment, LearnerProfile
from apps.learners.tests.helpers import make_world

URL = reverse("learners:profile")


class ProfilePageTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user("daniel", "daniel@example.com")
        self.profile = LearnerProfile.objects.create(user=self.user, preferred_name="Dani")
        self.world = make_world("Python Foundations")
        Enrollment.objects.create(learner=self.profile, world=self.world)

        other = make_user("ana", "ana@example.com")
        other_profile = LearnerProfile.objects.create(user=other, preferred_name="Ana Secret")
        Enrollment.objects.create(
            learner=other_profile,
            world=make_world("Other Learner World"),
            status=Enrollment.Status.PAUSED,
        )
        self.client.force_login(self.user)

    def test_requires_login(self) -> None:
        self.client.logout()
        self.assertRedirects(self.client.get(URL), f"{reverse('accounts:login')}?next={URL}")

    def test_shows_own_account_and_enrollments_only(self) -> None:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        for text in ("daniel", "daniel@example.com", 'value="Dani"', "Python Foundations"):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, "Status: </span>Active")
        for leaked in ("ana@example.com", "Ana Secret", "Other Learner World"):
            with self.subTest(leaked=leaked):
                self.assertNotContains(response, leaked)

    def test_update_preferred_name_and_timezone(self) -> None:
        response = self.client.post(
            URL, {"preferred_name": "Daniel I.", "timezone": "Europe/Bucharest"}
        )
        self.assertRedirects(response, URL, fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferred_name, "Daniel I.")
        self.assertEqual(self.profile.timezone, "Europe/Bucharest")
        self.assertContains(self.client.get(URL), "Your profile has been updated.")

    def test_invalid_timezone_is_rejected(self) -> None:
        response = self.client.post(URL, {"preferred_name": "Dani", "timezone": "Mars/Base"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("timezone", response.context["form"].errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.timezone, "UTC")

    def test_posting_cannot_touch_another_learner(self) -> None:
        other = LearnerProfile.objects.get(user__username="ana")
        self.client.post(
            URL, {"preferred_name": "Hacked", "timezone": "UTC", "user": other.user_id}
        )
        other.refresh_from_db()
        self.assertEqual(other.preferred_name, "Ana Secret")
        self.assertEqual(LearnerProfile.objects.get(user=self.user).preferred_name, "Hacked")

    def test_there_is_no_profile_route_by_id(self) -> None:
        with self.assertRaises(NoReverseMatch):
            reverse("learners:profile", args=[self.profile.pk])
        self.assertEqual(self.client.get(f"/profile/{self.profile.pk}/").status_code, 404)

    def test_profile_is_created_on_first_visit(self) -> None:
        newcomer = make_user("newcomer")
        self.client.force_login(newcomer)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(LearnerProfile.objects.filter(user=newcomer).exists())
        self.assertContains(response, "You haven't chosen a learning path yet.")
