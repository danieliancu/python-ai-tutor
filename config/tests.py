import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.env import env_bool, env_int, env_list


class HomeViewTests(TestCase):
    def test_home_returns_200(self) -> None:
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The application is running.")
        self.assertTemplateUsed(response, "home.html")


class HealthViewTests(SimpleTestCase):
    def test_health_returns_200(self) -> None:
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_rejects_post(self) -> None:
        response = self.client.post(reverse("health"))

        self.assertEqual(response.status_code, 405)


class AdminTests(TestCase):
    def test_admin_login_page_is_available(self) -> None:
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)


class EnvBoolTests(SimpleTestCase):
    def test_truthy_values(self) -> None:
        for value in ("1", "true", "TRUE", "yes", "on", " True "):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"FLAG": value}):
                self.assertTrue(env_bool("FLAG"))

    def test_falsy_values(self) -> None:
        for value in ("0", "false", "False", "no", "off"):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"FLAG": value}):
                self.assertFalse(env_bool("FLAG", default=True))

    def test_missing_or_empty_uses_default(self) -> None:
        with mock.patch.dict(os.environ, {"FLAG": ""}):
            self.assertTrue(env_bool("FLAG", default=True))
        with mock.patch.dict(os.environ, clear=True):
            self.assertFalse(env_bool("FLAG"))

    def test_invalid_value_raises(self) -> None:
        with (
            mock.patch.dict(os.environ, {"FLAG": "maybe"}),
            self.assertRaises(ImproperlyConfigured),
        ):
            env_bool("FLAG")


class EnvIntTests(SimpleTestCase):
    def test_parses_int(self) -> None:
        with mock.patch.dict(os.environ, {"NUM": " 42 "}):
            self.assertEqual(env_int("NUM"), 42)

    def test_invalid_value_raises(self) -> None:
        with mock.patch.dict(os.environ, {"NUM": "abc"}), self.assertRaises(ImproperlyConfigured):
            env_int("NUM")


class EnvListTests(SimpleTestCase):
    def test_trims_and_drops_empty_entries(self) -> None:
        with mock.patch.dict(os.environ, {"ITEMS": " a.com, ,b.com ,,"}):
            self.assertEqual(env_list("ITEMS"), ["a.com", "b.com"])

    def test_empty_uses_default(self) -> None:
        with mock.patch.dict(os.environ, {"ITEMS": " , "}):
            self.assertEqual(env_list("ITEMS", default=["x"]), ["x"])
        with mock.patch.dict(os.environ, clear=True):
            self.assertEqual(env_list("ITEMS"), [])
