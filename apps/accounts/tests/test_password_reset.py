import re

from django.contrib.auth import authenticate
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import PASSWORD, make_user

NEW_PASSWORD = "a-brand-new-passphrase-42"


class PasswordResetTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user("daniel", "daniel@example.com")

    def request_reset(self, email: str):
        return self.client.post(reverse("accounts:password_reset"), {"email": email})

    def test_request_page_renders(self) -> None:
        response = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'autocomplete="email"')

    def test_known_email_sends_a_reset_link(self) -> None:
        response = self.request_reset("DANIEL@example.com")
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["daniel@example.com"])
        self.assertEqual(message.subject, "Reset your Python AI Tutor password")
        self.assertIn("/accounts/reset/", message.body)
        self.assertNotIn(PASSWORD, message.body)

    def test_unknown_email_looks_the_same_and_sends_nothing(self) -> None:
        known = self.request_reset("daniel@example.com")
        unknown = self.request_reset("nobody@example.com")
        self.assertRedirects(unknown, reverse("accounts:password_reset_done"))
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known["Location"], unknown["Location"])
        self.assertEqual(len(mail.outbox), 1)

        done = self.client.get(unknown["Location"])
        self.assertContains(done, "If an account uses the address you entered")
        self.assertNotContains(done, "nobody@example.com")

    def test_link_sets_a_new_password(self) -> None:
        self.request_reset("daniel@example.com")
        link = re.search(r"https?://[^/]+(/accounts/reset/\S+/)", mail.outbox[0].body).group(1)

        # Django swaps the token for a session marker and redirects to a "set-password" URL.
        response = self.client.get(link, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")
        form_url = response.redirect_chain[-1][0]

        response = self.client.post(
            form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        complete = self.client.get(response["Location"])
        self.assertContains(complete, reverse("accounts:login"))

        self.assertIsNone(authenticate(username="daniel", password=PASSWORD))
        self.assertIsNotNone(authenticate(username="daniel", password=NEW_PASSWORD))

        # The link cannot be used twice.
        reused = self.client.get(link, follow=True)
        self.assertContains(reused, "This link has expired")

    def test_invalid_link_shows_a_friendly_state(self) -> None:
        url = reverse(
            "accounts:password_reset_confirm", kwargs={"uidb64": "MQ", "token": "bad-token"}
        )
        response = self.client.get(url)
        self.assertContains(response, "This link has expired")
        self.assertContains(response, reverse("accounts:password_reset"))
