from django.contrib.auth import get_user
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.helpers import PASSWORD, make_user
from apps.learners.models import LearnerProfile

URL = reverse("accounts:login")


class LoginTests(TestCase):
    def setUp(self) -> None:
        self.user = make_user("daniel", "Daniel@Example.com")

    def complete_onboarding(self) -> None:
        LearnerProfile.objects.create(user=self.user, onboarding_completed_at=timezone.now())

    def login(self, identifier: str, password: str = PASSWORD, **extra):
        return self.client.post(URL, {"username": identifier, "password": password, **extra})

    def assert_logged_in(self) -> None:
        self.assertEqual(get_user(self.client).pk, self.user.pk)

    def test_page_renders(self) -> None:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email or username")
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, reverse("accounts:password_reset"))

    def test_login_with_username(self) -> None:
        self.complete_onboarding()
        self.assertRedirects(self.login("daniel"), reverse("home"), fetch_redirect_response=False)
        self.assert_logged_in()

    def test_login_with_email_is_case_insensitive(self) -> None:
        self.complete_onboarding()
        for identifier in ("Daniel@Example.com", "daniel@example.com", " DANIEL@EXAMPLE.COM "):
            with self.subTest(identifier=identifier):
                self.client.logout()
                self.assertRedirects(
                    self.login(identifier), reverse("home"), fetch_redirect_response=False
                )
                self.assert_logged_in()

    def test_wrong_password_fails_without_revealing_which_part(self) -> None:
        for identifier in ("daniel", "daniel@example.com", "nobody@example.com"):
            with self.subTest(identifier=identifier):
                response = self.login(identifier, "wrong-password")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "don&#x27;t match")
                self.assertFalse(get_user(self.client).is_authenticated)

    def test_username_that_looks_like_an_email_wins_over_email_lookup(self) -> None:
        owner = make_user("shared@example.com", "owner@example.com")
        make_user("someone-else", "shared@example.com")
        LearnerProfile.objects.create(user=owner, onboarding_completed_at=timezone.now())
        self.login("shared@example.com")
        self.assertEqual(get_user(self.client).pk, owner.pk)

    def test_inactive_user_cannot_log_in(self) -> None:
        self.user.is_active = False
        self.user.save()
        response = self.login("daniel")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user(self.client).is_authenticated)

    def test_incomplete_onboarding_redirects_to_onboarding(self) -> None:
        self.assertRedirects(
            self.login("daniel", next="/profile/"),
            reverse("learners:onboarding"),
            fetch_redirect_response=False,
        )
        self.assert_logged_in()
        # Logging in never creates a learner profile by itself.
        self.assertFalse(LearnerProfile.objects.exists())

    def test_completed_onboarding_honours_safe_next(self) -> None:
        self.complete_onboarding()
        response = self.login("daniel", next=reverse("learners:profile"))
        self.assertRedirects(response, reverse("learners:profile"))

    def test_unsafe_next_is_ignored(self) -> None:
        self.complete_onboarding()
        for unsafe in ("https://evil.example/", "//evil.example/", "http://evil.example/x"):
            with self.subTest(next=unsafe):
                self.client.logout()
                response = self.login("daniel", next=unsafe)
                self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_signed_in_user_visiting_login_is_redirected(self) -> None:
        self.complete_onboarding()
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(URL), reverse("home"), fetch_redirect_response=False)

    def test_login_required_pages_send_anonymous_users_to_login(self) -> None:
        for name in ("learners:profile", "learners:onboarding"):
            with self.subTest(page=name):
                url = reverse(name)
                self.assertRedirects(self.client.get(url), f"{URL}?next={url}")
