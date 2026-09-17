import importlib.util
import sys
from unittest import mock

from django.conf import global_settings
from django.contrib.auth import get_user
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.helpers import PASSWORD, make_user
from apps.learners.models import LearnerProfile
from config import settings as config_settings

URL = reverse("accounts:signup")


def project_settings_without_test_override():
    """Load config/settings.py fresh, as a non-test command (e.g. runserver) would."""
    spec = importlib.util.spec_from_file_location("_settings_probe", config_settings.__file__)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "argv", ["manage.py", "runserver"]):
        spec.loader.exec_module(module)
    return module


def signup_data(**overrides) -> dict:
    data = {
        "username": "newlearner",
        "email": "New.Learner@Example.COM",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class SignUpTests(TestCase):
    def test_page_renders_with_accessible_fields(self) -> None:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, 'autocomplete="email"')
        self.assertContains(response, 'autocomplete="new-password"', count=2)
        self.assertContains(response, '<label class="field__label" for="id_username">')

    def test_valid_signup_creates_user_profile_and_logs_in(self) -> None:
        response = self.client.post(URL, signup_data())

        self.assertRedirects(response, reverse("learners:onboarding"))
        user = User.objects.get()
        self.assertEqual(user.username, "newlearner")
        self.assertEqual(user.email, "New.Learner@example.com")
        self.assertTrue(LearnerProfile.objects.filter(user=user).exists())
        self.assertEqual(get_user(self.client).pk, user.pk)

    def test_password_is_hashed(self) -> None:
        self.client.post(URL, signup_data())
        user = User.objects.get()
        self.assertNotIn(PASSWORD, user.password)
        # Stored in Django's "<algorithm>$..." format by the configured hasher.
        self.assertEqual(identify_hasher(user.password).algorithm, get_hasher().algorithm)
        self.assertTrue(user.check_password(PASSWORD))

    def test_production_settings_use_standard_django_hashing(self) -> None:
        self.assertEqual(
            global_settings.PASSWORD_HASHERS[0],
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        )
        self.assertFalse(hasattr(project_settings_without_test_override(), "PASSWORD_HASHERS"))

    def assert_rejected(self, data: dict, field: str, message: str) -> None:
        response = self.client.post(URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors)
        self.assertContains(response, message)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertFalse(get_user(self.client).is_authenticated)

    def test_missing_email_is_rejected(self) -> None:
        self.assert_rejected(signup_data(email=""), "email", "This field is required.")
        self.assertFalse(User.objects.exists())

    def test_duplicate_username_is_rejected(self) -> None:
        make_user("newlearner", "someone@example.com")
        self.assert_rejected(signup_data(), "username", "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_is_rejected_case_insensitively(self) -> None:
        for existing in ("new.learner@example.com", "NEW.LEARNER@EXAMPLE.COM"):
            with self.subTest(existing=existing):
                User.objects.all().delete()
                make_user("original", existing)
                self.assert_rejected(
                    signup_data(), "email", "An account with this email address already exists."
                )
                self.assertEqual(User.objects.count(), 1)

    def test_weak_or_mismatched_passwords_are_rejected(self) -> None:
        self.assert_rejected(
            signup_data(password1="123", password2="123"), "password2", "too short"
        )
        self.assert_rejected(signup_data(password2="different-pass-987"), "password2", "match")
        self.assertFalse(User.objects.exists())
        self.assertFalse(LearnerProfile.objects.exists())

    def test_signed_in_user_is_sent_home(self) -> None:
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(URL), reverse("home"), fetch_redirect_response=False)
