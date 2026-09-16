import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learners.models import LearnerProfile
from config.env import env_bool, env_int, env_list


class HomeViewTests(TestCase):
    def test_home_returns_200(self) -> None:
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The application is running.")
        self.assertTemplateUsed(response, "home.html")


class ProductShellTests(TestCase):
    def setUp(self) -> None:
        self.response = self.client.get(reverse("home"))

    def test_root_url_returns_200(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")

    def test_lesson_title_renders(self) -> None:
        self.assertContains(self.response, '<h1 id="lesson-title">Loops</h1>', html=True)
        self.assertContains(self.response, "Lesson 4 of 8")

    def test_primary_run_code_action_renders(self) -> None:
        self.assertContains(self.response, 'class="btn-run"')
        self.assertContains(self.response, "Run Code")

    def test_current_skill_renders(self) -> None:
        self.assertContains(self.response, "Current skill")
        self.assertContains(self.response, "<dd>Loops</dd>", html=True)
        self.assertContains(self.response, 'aria-current="step"', count=1)

    def test_python_mastery_renders(self) -> None:
        self.assertContains(self.response, "Python Mastery")
        self.assertContains(self.response, "31%")

    def test_static_demo_stats_render(self) -> None:
        for text in (
            '<span class="stat__word">Level </span>14',
            "XP</span> 7,840",
            '12<span class="stat__word"> days</span>',
            "<dd>12 days</dd>",
        ):
            with self.subTest(text=text):
                self.assertContains(self.response, text)

    def test_skill_map_statuses_are_text_not_only_colour(self) -> None:
        for status in ("MASTERED", "PRACTISING", "LEARNING", "LOCKED"):
            with self.subTest(status=status):
                self.assertContains(self.response, status)
        for skill in ("Variables", "Conditions", "Lists", "Functions", "OOP"):
            with self.subTest(skill=skill):
                self.assertContains(self.response, skill)

    def test_exercise_and_tutor_render(self) -> None:
        self.assertContains(self.response, "Coding Exercise")
        self.assertContains(self.response, "Print only numbers greater than 10")
        self.assertContains(self.response, "main.py")
        self.assertContains(self.response, "AI Tutor")
        self.assertContains(self.response, "Look again at the loop condition.")
        self.assertContains(self.response, "Build a Number Analyzer")

    def test_primary_navigation_renders(self) -> None:
        for label in ("Learn", "Practice", "Projects", "Community"):
            with self.subTest(label=label):
                self.assertContains(self.response, label)
        self.assertContains(self.response, 'aria-current="page">Learn</a>')

    def test_demo_controls_are_marked_inactive(self) -> None:
        self.assertContains(self.response, 'id="demo-note"')
        self.assertContains(self.response, 'aria-describedby="demo-note"')

    def test_major_landmarks_are_present(self) -> None:
        for fragment in (
            '<header class="topbar">',
            '<nav class="primary-nav" aria-label="Primary">',
            'role="search"',
            '<main id="lesson"',
            'aria-label="Breadcrumb"',
            '<aside id="progress" class="side-progress"',
            'aria-label="Skill map"',
            '<aside id="tutor" class="side-tutor"',
            '<h1 id="lesson-title">',
            'class="skip-link" href="#lesson"',
            "<footer",
        ):
            with self.subTest(fragment=fragment):
                self.assertContains(self.response, fragment)

    def test_health_still_works(self) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class HomeAuthAwareTests(TestCase):
    def test_anonymous_visitor_sees_sign_in(self) -> None:
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<a class="signin-link" href="{reverse("accounts:login")}"')
        self.assertNotContains(response, reverse("accounts:logout"))
        self.assertNotContains(response, "account-menu")

    def test_signed_in_learner_sees_account_menu(self) -> None:
        user = User.objects.create_user("daniel", "daniel@example.com", "pass-12345-word")
        LearnerProfile.objects.create(user=user, preferred_name="Dani")
        self.client.force_login(user)

        response = self.client.get(reverse("home"))
        self.assertContains(response, 'aria-label="Account menu for Dani"')
        self.assertContains(response, f'href="{reverse("learners:profile")}"')
        self.assertContains(response, f'<form method="post" action="{reverse("accounts:logout")}">')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, "signin-link")

    def test_username_is_used_without_creating_a_profile(self) -> None:
        user = User.objects.create_user("noprofile", "np@example.com", "pass-12345-word")
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Account menu for noprofile")
        self.assertFalse(LearnerProfile.objects.exists())

    def test_demo_progress_is_unchanged_for_signed_in_users(self) -> None:
        user = User.objects.create_user("daniel", "daniel@example.com", "pass-12345-word")
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        for text in ("31%", "XP</span> 7,840", "<dd>12 days</dd>", "Run Code"):
            with self.subTest(text=text):
                self.assertContains(response, text)


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
