"""Phase 9 in the course player: platform branding, course identity and real gamification."""

import re

from django.test import Client, TestCase
from django.urls import reverse

from apps.attempts.tests.helpers import SECRET_OPTION
from apps.course_player.tests.helpers import PlayerFixtures, page_config, player_url
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.gamification.models import BossChallenge

TITLE = re.compile(r"<title>(.*?)</title>", re.S)


class BrandingTests(PlayerFixtures, TestCase):
    def test_platform_brand_and_course_identity(self) -> None:
        html = self.open(self.mcq).content.decode()
        lesson = self.mcq.lesson
        self.assertEqual(
            TITLE.search(html).group(1),
            f"{lesson.title} · Python Foundations · cursuri.net",
        )
        self.assertIn('<span class="brand__name">cursuri.net</span>', html)
        self.assertIn(">Python Foundations Mastery</h2>", html)
        self.assertIn("<span>Python Foundations</span>", html)  # breadcrumb
        self.assertIn("cursuri.net · Learn one step at a time.", html)
        self.assertNotIn("Python AI Tutor", html)
        self.assertIn("AI Tutor", html)  # the feature keeps its name

    def test_each_course_keeps_its_own_name(self) -> None:
        django_lesson = make_lesson_chain("Django Web Apps", domain="django")
        world = django_lesson.concept.skill.world
        self.enroll(world)
        make_exercise(
            django_lesson,
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            evaluation_spec={"correct_option": "a"},
        )
        for course, title in (
            (self.python_world, "Python Foundations"),
            (world, "Django Web Apps"),
        ):
            with self.subTest(course=title):
                response = self.open(world=course)
                html = response.content.decode()
                self.assertTrue(TITLE.search(html).group(1).endswith(f" · {title} · cursuri.net"))
                self.assertIn(f">{title} Mastery</h2>", html)
                self.assertIn(f"<span>{title}</span>", html)
                self.assertIn('<span class="brand__name">cursuri.net</span>', html)
                self.assertEqual(response.context["course"]["title"], title)
                self.assertEqual(response.context["course"]["domain"], course.domain)
        django_html = self.open(world=world).content.decode()
        self.assertNotIn("Python", django_html)

    def test_public_pages_use_the_platform_brand(self) -> None:
        anonymous = Client()
        for url in (
            reverse("home"),
            reverse("accounts:login"),
            reverse("accounts:signup"),
            reverse("accounts:password_reset"),
        ):
            with self.subTest(url=url):
                html = anonymous.get(url).content.decode()
                self.assertIn("cursuri.net", html)
                self.assertNotIn("Python AI Tutor", html)
        demo = anonymous.get(reverse("home")).content.decode()
        self.assertIn("<title>Loops · Python Foundations · cursuri.net</title>", demo)


class HeaderStatsTests(PlayerFixtures, TestCase):
    def test_real_stats_in_the_header(self) -> None:
        html = self.open(self.mcq).content.decode()
        self.assertIn("<span data-stat-xp>0</span>", html)
        self.assertIn("<span data-stat-level>1</span>", html)
        self.assertIn("<span data-stat-streak>0</span>", html)
        self.assertIn('stroke-dasharray="0 100"', html)
        self.assertNotIn("—</span>", html)

        self.attempt(self.mcq, {"answer": SECRET_OPTION})
        # Earned XP shows up without signing out (the page and the refresh fragment).
        html = self.open(self.mcq).content.decode()
        self.assertIn("<span data-stat-xp>30</span>", html)
        self.assertIn("<span data-stat-streak>1</span>", html)
        self.assertIn('stroke-dasharray="30 100" transform="rotate(-90 10 10)"', html)
        fragment = self.client.get(
            reverse("course_player:progress", args=[self.python_world.pk])
        ).content.decode()
        self.assertIn("<dt>XP</dt><dd>30</dd>", fragment)
        self.assertIn("<dt>Streak</dt><dd>1 days</dd>", fragment)

    def test_config_points_at_the_gamification_summary(self) -> None:
        config = page_config(self.open(self.mcq))
        self.assertEqual(config["urls"]["gamification"], reverse("gamification:summary"))
        self.assertEqual(config["bossExerciseIds"], [])
        self.assertEqual(config["text"]["bossBadge"], "Boss Challenge")


class BossPresentationTests(PlayerFixtures, TestCase):
    def test_boss_exercise_is_labelled(self) -> None:
        BossChallenge.objects.create(exercise=self.gap)
        response = self.open(self.gap)
        self.assertContains(response, '<p class="exercise__kicker">Boss Challenge')
        self.assertEqual(page_config(response)["bossExerciseIds"], [self.gap.pk])
        self.assertNotContains(self.open(self.mcq), '<p class="exercise__kicker">Boss Challenge')

    def test_next_up_names_a_boss_only_when_next_best_action_picks_it(self) -> None:
        default = self.open()
        picked = page_config(default)["exercise"]["id"]
        BossChallenge.objects.create(exercise_id=picked)
        response = self.open()
        self.assertEqual(page_config(response)["exercise"]["id"], picked)  # same choice
        self.assertEqual(response.context["lesson"]["next_up"]["badge"], "Boss Challenge")
        self.assertEqual(
            response.context["lesson"]["next_up"]["href"],
            player_url(self.python_world) + f"?exercise={picked}",
        )
