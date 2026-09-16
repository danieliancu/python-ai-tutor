from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.helpers import make_user
from apps.learners.models import Enrollment, LearnerProfile
from apps.learners.tests.helpers import make_world


class LearnerAdminTests(TestCase):
    def setUp(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        self.profile = LearnerProfile.objects.create(
            user=make_user("daniel", "daniel@example.com"), preferred_name="Dani"
        )
        self.enrollment = Enrollment.objects.create(
            learner=self.profile, world=make_world("Python Foundations")
        )

    def test_pages_render(self) -> None:
        for name, obj in (("learnerprofile", self.profile), ("enrollment", self.enrollment)):
            for view, args in (("changelist", []), ("add", []), ("change", [obj.pk])):
                with self.subTest(model=name, view=view):
                    url = reverse(f"admin:learners_{name}_{view}", args=args)
                    self.assertEqual(self.client.get(url).status_code, 200)

    def result_count(self, url: str, params: dict) -> int:
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return response.context["cl"].result_count

    def test_search_and_filters(self) -> None:
        url = reverse("admin:learners_learnerprofile_changelist")
        self.assertEqual(self.result_count(url, {"q": "daniel@example.com"}), 1)
        self.assertEqual(self.result_count(url, {"q": "Dani"}), 1)
        self.assertEqual(self.result_count(url, {"q": "nobody"}), 0)
        self.assertEqual(self.result_count(url, {"onboarding_completed_at__isempty": "1"}), 1)

        url = reverse("admin:learners_enrollment_changelist")
        self.assertEqual(self.result_count(url, {"status__exact": "active", "q": "Python"}), 1)
        self.assertEqual(self.result_count(url, {"q": "daniel@example.com"}), 1)
        self.assertEqual(self.result_count(url, {"status__exact": "paused"}), 0)
