from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_custom_user_model_is_active(self) -> None:
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertIs(get_user_model(), User)

    def test_create_user(self) -> None:
        user = User.objects.create_user(
            username="alice", email="alice@example.com", password="s3cure-pass-123"
        )

        self.assertEqual(user.username, "alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, "s3cure-pass-123")
        self.assertTrue(user.check_password("s3cure-pass-123"))
        self.assertEqual(str(user), "alice")

    def test_create_superuser(self) -> None:
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="s3cure-pass-123"
        )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class AuthenticationTests(TestCase):
    password = "correct-horse-battery-staple"

    def test_signup_creates_and_logs_in_user(self) -> None:
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newlearner",
                "email": "LEARNER@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="newlearner")
        self.assertEqual(user.email, "learner@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_requires_unique_email_ignoring_case(self) -> None:
        User.objects.create_user("existing", "learner@example.com", self.password)

        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "another",
                "email": "Learner@Example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertFalse(User.objects.filter(username="another").exists())

    def test_authenticated_user_is_redirected_from_signup(self) -> None:
        user = User.objects.create_user("learner", "learner@example.com", self.password)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:signup"))

        self.assertRedirects(response, reverse("home"))

    def test_login_and_logout(self) -> None:
        User.objects.create_user("learner", "learner@example.com", self.password)

        login_response = self.client.post(
            reverse("accounts:login"), {"username": "learner", "password": self.password}
        )
        self.assertRedirects(login_response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

        logout_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_does_not_accept_get(self) -> None:
        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)

    def test_password_reset_sends_email_without_disclosing_account(self) -> None:
        User.objects.create_user("learner", "learner@example.com", self.password)

        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "learner@example.com"}
        )

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
