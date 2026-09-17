from django.test import Client, TestCase
from django.urls import reverse

from apps.curriculum.tests.helpers import make_world
from apps.learners.models import Enrollment, EnrollmentStatus
from apps.projects.models import Project
from apps.projects.tests.helpers import GOOD, ProjectFixtures


class ProjectAccessTests(ProjectFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.master()
        self.client.force_login(self.user)

    def pages(self):
        return [
            reverse("projects:list", args=[self.world.pk]),
            self.url("detail"),
            self.url("stage", self.stages[0]),
        ]

    def json_posts(self):
        stage = self.stages[0]
        return [
            (self.url("draft"), {"stage": stage.slug, "source": GOOD}),
            (self.url("submit", stage), {"source": GOOD}),
            (self.url("coach", stage), {"intent": "hint"}),
        ]

    def test_anonymous_is_sent_to_login_or_refused(self) -> None:
        anonymous = Client()
        for url in self.pages():
            with self.subTest(url=url):
                response = anonymous.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])
        for url, body in self.json_posts():
            with self.subTest(url=url):
                self.assertEqual(self.post(url, body, anonymous).status_code, 401)

    def test_active_and_completed_enrollments_are_allowed(self) -> None:
        for status in (EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED):
            Enrollment.objects.filter(pk=self.enrollment.pk).update(status=status)
            for url in self.pages():
                with self.subTest(status=status, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_paused_enrollment_is_denied(self) -> None:
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status=EnrollmentStatus.PAUSED)
        for url in self.pages():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url, body in self.json_posts():
            with self.subTest(url=url):
                response = self.post(url, body)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": "forbidden"})

    def test_learners_without_an_enrollment_are_denied(self) -> None:
        stranger = Client()
        stranger.force_login(self.enroll_other("stranger")[0])
        Enrollment.objects.filter(learner__user__username="stranger").delete()
        for url in self.pages():
            self.assertEqual(stranger.get(url).status_code, 403)
        for url, body in self.json_posts():
            self.assertEqual(self.post(url, body, stranger).status_code, 403)

    def test_cross_world_project_is_not_found(self) -> None:
        other_world = make_world("Django")
        Enrollment.objects.create(learner=self.profile, world=other_world)
        for url in (
            self.url("detail", world=other_world),
            self.url("stage", self.stages[0], world=other_world),
        ):
            self.assertEqual(self.client.get(url).status_code, 404)
        response = self.post(
            self.url("submit", self.stages[0], world=other_world), {"source": GOOD}
        )
        self.assertEqual(response.status_code, 404)

    def test_unpublished_project_and_stage_are_not_found(self) -> None:
        Project.objects.filter(pk=self.project.pk).update(is_published=False)
        self.assertEqual(self.client.get(self.url("detail")).status_code, 404)
        self.assertEqual(self.submit(self.stages[0]).status_code, 404)
        Project.objects.filter(pk=self.project.pk).update(is_published=True)
        self.stages[0].is_published = False
        self.stages[0].save()
        self.assertEqual(self.client.get(self.url("stage", self.stages[0])).status_code, 404)
        self.assertEqual(self.client.get("/learn/worlds/999999/projects/").status_code, 404)

    def test_json_endpoints_are_post_only_with_clean_bodies(self) -> None:
        stage = self.stages[0]
        self.assertEqual(self.client.get(self.url("submit", stage)).status_code, 405)
        response = self.client.post(
            self.url("submit", stage), data="nope", content_type="application/json"
        )
        self.assertEqual(response.json(), {"error": "malformed_json"})
        response = self.post(self.url("submit", stage), {"source": GOOD, "xp": 999})
        self.assertEqual(response.json(), {"error": "unknown_fields"})
        response = self.post(self.url("draft"), {"stage": "nope", "source": GOOD})
        self.assertEqual(response.status_code, 404)

    def test_csrf_is_enforced(self) -> None:
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for url, body in self.json_posts():
            with self.subTest(url=url):
                self.assertEqual(self.post(url, body, strict).status_code, 403)
        page = strict.get(self.url("stage", self.stages[0]))
        token = page.cookies["csrftoken"].value
        response = strict.post(
            self.url("draft"),
            data='{"stage": "stage-1", "source": "x = 1"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
