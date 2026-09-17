from django.test import TestCase
from django.urls import reverse

from apps.curriculum.tests.helpers import make_world
from apps.gamification.models import GamificationProfile, XPEvent
from apps.learners.models import Enrollment
from apps.projects import selectors
from apps.projects.models import Project, ProjectDraft
from apps.projects.tests.helpers import ProjectFixtures


class AvailabilityTests(ProjectFixtures, TestCase):
    def state(self):
        return selectors.project_view(self.enrollment, self.project).state

    def test_locked_until_every_requirement_is_met(self) -> None:
        self.assertEqual(self.state(), selectors.LOCKED)
        self.master(self.concept_a, score=90)
        self.master(self.concept_b, score=64.99)
        self.assertEqual(self.state(), selectors.LOCKED)
        self.master(self.concept_b, score=65)
        self.assertEqual(self.state(), selectors.AVAILABLE)

    def test_requirement_rows_explain_the_lock(self) -> None:
        self.master(self.concept_a, score=70)
        view = selectors.project_view(self.enrollment, self.project)
        rows = [(r.concept, r.current, r.required, r.met) for r in view.requirements]
        self.assertIn((self.concept_a.title, 70, 65, True), rows)
        self.assertIn(("Loops", 0, 65, False), rows)
        self.assertEqual([r.concept for r in view.missing_requirements], ["Loops"])

    def test_no_requirements_means_available(self) -> None:
        self.project.requirements.all().delete()
        self.assertEqual(self.state(), selectors.AVAILABLE)

    def test_gamification_never_unlocks_a_project(self) -> None:
        GamificationProfile.objects.create(
            learner=self.profile, total_xp=99999, current_streak=50, longest_streak=50
        )
        XPEvent.objects.create(
            learner=self.profile,
            world=self.world,
            event_type="skill_mastered",
            xp=99999,
            source_key="fake",
        )
        self.assertEqual(self.state(), selectors.LOCKED)

    def test_started_work_stays_reachable_if_mastery_dips(self) -> None:
        self.master()
        ProjectDraft.objects.create(enrollment=self.enrollment, project=self.project)
        self.master(score=10)
        self.assertEqual(self.state(), selectors.IN_PROGRESS)

    def test_locked_projects_have_no_available_stages(self) -> None:
        view = selectors.project_view(self.enrollment, self.project)
        self.assertFalse(any(stage.available for stage in view.stages))
        self.client.force_login(self.user)
        response = self.client.get(self.url("stage", self.stages[0]))
        self.assertRedirects(response, self.url("detail"))
        response = self.submit(self.stages[0])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"error": "project_locked"})


class ProjectListTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_list_shows_state_progress_and_requirements(self) -> None:
        response = self.client.get(reverse("projects:list", args=[self.world.pk]))
        self.assertContains(response, "Area Tool")
        self.assertContains(response, "Locked")
        self.assertContains(response, "Requires:")
        self.assertContains(response, "0% / 65%")
        self.assertContains(response, "0 of 3 stages · 0%")
        self.assertContains(response, "150 XP")
        self.assertNotContains(response, self.url("detail"))  # locked cards aren't links

        self.master()
        self.submit(self.stages[0])
        response = self.client.get(reverse("projects:list", args=[self.world.pk]))
        self.assertContains(response, "In progress")
        self.assertContains(response, "1 of 3 stages · 33%")
        self.assertContains(response, self.url("detail"))

    def test_projects_stay_in_their_world(self) -> None:
        django = make_world("Django", domain="django")
        Enrollment.objects.create(learner=self.profile, world=django)
        response = self.client.get(reverse("projects:list", args=[django.pk]))
        self.assertContains(response, "No projects are available for this course yet.")
        self.assertNotContains(response, "Area Tool")
        self.assertContains(response, "Django Projects")

    def test_unpublished_projects_are_hidden(self) -> None:
        Project.objects.filter(pk=self.project.pk).update(is_published=False)
        response = self.client.get(reverse("projects:list", args=[self.world.pk]))
        self.assertNotContains(response, "Area Tool")

    def test_query_count_does_not_grow_with_projects(self) -> None:
        url = reverse("projects:list", args=[self.world.pk])
        self.client.get(url)
        with self.assertNumQueries(26) as first:
            self.client.get(url)
        for n in range(2, 6):
            copy = Project.objects.create(
                world=self.world,
                title=f"Copy {n}",
                slug=f"copy-{n}",
                summary="s",
                brief="b",
                order=n,
                estimated_minutes=5,
                is_published=True,
            )
            copy.requirements.create(concept=self.concept_a)
        with self.assertNumQueries(len(first.captured_queries)):
            self.client.get(url)
