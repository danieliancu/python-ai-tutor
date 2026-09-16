from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.attempts.models import AttemptMistake
from apps.attempts.tests.helpers import AttemptFixtures


class AttemptAdminTests(AttemptFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.attempt = self.record(self.gap, "wrong")
        self.mistake = AttemptMistake.objects.get()
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)

    def test_pages_render(self) -> None:
        for url in (
            reverse("admin:attempts_exerciseattempt_changelist"),
            reverse("admin:attempts_exerciseattempt_change", args=[self.attempt.pk]),
            reverse("admin:attempts_attemptmistake_changelist"),
            reverse("admin:attempts_attemptmistake_change", args=[self.mistake.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
        detail = self.client.get(
            reverse("admin:attempts_exerciseattempt_change", args=[self.attempt.pk])
        )
        self.assertContains(detail, "incorrect_value")

    def test_filters_and_search(self) -> None:
        url = reverse("admin:attempts_exerciseattempt_changelist")
        for params, count in (
            ({"status__exact": "incorrect"}, 1),
            ({"status__exact": "correct"}, 0),
            ({"evaluator": "fill_gap"}, 1),
            ({"q": "learner"}, 1),
            ({"q": self.gap.slug}, 1),
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).context["cl"].result_count, count)

    def test_records_cannot_be_added_or_edited(self) -> None:
        self.assertEqual(
            self.client.get(reverse("admin:attempts_exerciseattempt_add")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("admin:attempts_attemptmistake_add")).status_code, 403
        )
        response = self.client.post(
            reverse("admin:attempts_exerciseattempt_change", args=[self.attempt.pk]),
            {"status": "correct"},
        )
        self.assertEqual(response.status_code, 403)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "incorrect")
