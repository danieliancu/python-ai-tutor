from django.contrib.auth import get_user
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user

URL = reverse("accounts:logout")


class LogoutTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user()

    def test_post_logs_out_and_redirects_home(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(URL)
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(get_user(self.client).is_authenticated)

    def test_get_is_not_allowed_and_keeps_the_session(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(get_user(self.client).is_authenticated)

    def test_post_without_csrf_token_is_rejected(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(URL)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(get_user(client).is_authenticated)
