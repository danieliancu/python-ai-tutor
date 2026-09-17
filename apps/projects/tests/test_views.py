import re
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import dateformat, timezone

from apps.accounts.models import User
from apps.course_player.tests.helpers import PlayerFixtures
from apps.curriculum.models import Concept, World
from apps.projects.data.python_foundations import PROJECTS
from apps.projects.evaluation.spec import stage_spec_errors
from apps.projects.models import Project, ProjectCompletion, ProjectStage
from apps.projects.tests.helpers import (
    SECRET_DRIVER,
    SECRET_FIXTURE,
    ProjectFixtures,
)

TITLE = re.compile(r"<title>(.*?)</title>", re.S)
PRIVATE_WORDS = ("evaluation_spec", "expected_stdout", "driver", "fixtures", SECRET_DRIVER)


class ProjectPagesTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)

    def test_branding_and_course_identity(self) -> None:
        pages = {
            reverse("projects:list", args=[self.world.pk]): "Projects",
            self.url("detail"): "Area Tool",
            self.url("stage", self.stages[0]): "Stage 1 · Area Tool",
        }
        for url, page in pages.items():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertEqual(
                    TITLE.search(html).group(1), f"{page} · Python Foundations · cursuri.net"
                )
                self.assertIn('<span class="brand__name">cursuri.net</span>', html)
                self.assertIn(">Python Foundations Mastery</h2>", html)
                self.assertNotIn("Python AI Tutor", html)
                self.assertIn(
                    f'<a href="{reverse("projects:list", args=[self.world.pk])}" '
                    'aria-current="page">Projects</a>',
                    html,
                )
                self.assertIn('class="topbar"', html)
                self.assertIn('class="shell"', html)

    def test_workspace_shows_the_stage_and_hides_private_data(self) -> None:
        response = self.client.get(self.url("stage", self.stages[0]))
        html = response.content.decode()
        for text in (
            "Stage 1 of 3",
            "Objective 1",
            "Instructions 1",
            "Requirement 1",
            "Run / Check",
        ):
            self.assertIn(text, html)
        self.assertIn('src="/static/js/projects.js"', html)
        for word in PRIVATE_WORDS:
            self.assertNotIn(word, html)
        self.assertNotIn("SECRET-FIXTURE-ROW", html)
        self.assertNotIn(SECRET_FIXTURE, html)
        self.assertEqual(html.count("innerHTML"), 0)

    def test_learner_code_and_feedback_are_escaped(self) -> None:
        source = "def area(w, h):\n    return w * h  # </textarea><script>alert(1)</script>\n"
        self.submit(self.stages[0], source)
        html = self.client.get(self.url("stage", self.stages[0])).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;/textarea&gt;&lt;script&gt;", html)

    def test_completed_project_shows_on_profile(self) -> None:
        self.complete_all()
        completion = ProjectCompletion.objects.get()
        response = self.client.get(reverse("learners:profile"))
        self.assertContains(response, "Area Tool")
        self.assertContains(
            response,
            "Python Foundations · Completed "
            + dateformat.format(timezone.localtime(completion.completed_at), "j M Y"),
        )

    def test_profile_without_projects(self) -> None:
        self.assertContains(
            self.client.get(reverse("learners:profile")), "No completed projects yet."
        )

    def test_admin_pages(self) -> None:
        self.complete_all()
        admin = User.objects.create_superuser("admin", "admin@example.com", "pass-12345")
        self.client.force_login(admin)
        for name, obj in (
            ("project", self.project),
            ("projectstage", self.stages[0]),
            ("projectconceptrequirement", self.project.requirements.first()),
            ("projectdraft", self.project.drafts.first()),
            ("projectsubmission", self.project.submissions.first()),
            ("projectcompletion", ProjectCompletion.objects.get()),
        ):
            for url in (
                reverse(f"admin:projects_{name}_changelist"),
                reverse(f"admin:projects_{name}_change", args=[obj.pk]),
            ):
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
        page = self.client.get(
            reverse("admin:projects_projectstage_change", args=[self.stages[0].pk])
        )
        self.assertContains(page, "Evaluation (private, never shown to learners or the AI tutor)")


class CoursePlayerNavTests(PlayerFixtures, TestCase):
    def test_learn_page_links_to_this_worlds_projects(self) -> None:
        html = self.open(self.mcq).content.decode()
        projects_url = reverse("projects:list", args=[self.python_world.pk])
        self.assertIn(f'<a href="{projects_url}">Projects</a>', html)
        self.assertIn('aria-current="page">Learn</a>', html)
        demo = self.client_class().get(reverse("home")).content.decode()
        self.assertIn('aria-describedby="demo-note">Projects</button>', demo)
        self.assertNotIn("/projects/", demo)


class SeedTests(TestCase):
    def test_seed_creates_the_python_projects_idempotently(self) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        out = StringIO()
        call_command("seed_python_projects", stdout=out)
        self.assertIn("5 created", out.getvalue())
        world = World.objects.get(slug="python-foundations")
        projects = list(Project.objects.filter(world=world).order_by("order"))
        self.assertEqual(
            [p.title for p in projects],
            [
                "Number Analyzer",
                "Contact Book",
                "Expense Tracker",
                "Inventory Manager",
                "Personal Finance Manager",
            ],
        )
        self.assertEqual(
            [(p.difficulty, p.xp_reward, p.stages.count()) for p in projects],
            [
                ("beginner", 100, 4),
                ("beginner", 150, 4),
                ("intermediate", 200, 4),
                ("intermediate", 200, 4),
                ("advanced", 250, 5),
            ],
        )
        for stage in ProjectStage.objects.all():
            with self.subTest(stage=stage.slug):
                self.assertEqual(stage_spec_errors(stage.evaluation_spec), [])
                self.assertNotIn("reference_solution", str(stage.evaluation_spec))
        for project, definition in zip(projects, PROJECTS, strict=True):
            paths = {
                f"{r.concept.skill.slug}/{r.concept.slug}"
                for r in project.requirements.select_related("concept__skill")
            }
            self.assertEqual(paths, set(definition["requirements"]))
            self.assertTrue(all(r.minimum_mastery == 65 for r in project.requirements.all()))

        before = list(ProjectStage.objects.order_by("id").values_list("id", "order"))
        call_command("seed_python_projects", stdout=StringIO())
        self.assertEqual(
            list(ProjectStage.objects.order_by("id").values_list("id", "order")), before
        )
        self.assertEqual(Project.objects.count(), 5)

    def test_missing_curriculum_is_reported(self) -> None:
        with self.assertRaisesMessage(CommandError, "seed_curriculum"):
            call_command("seed_python_projects", stdout=StringIO())
        call_command("seed_curriculum", stdout=StringIO())
        Concept.objects.filter(slug="csv").delete()
        with self.assertRaisesMessage(CommandError, "real-data/csv"):
            call_command("seed_python_projects", stdout=StringIO())
