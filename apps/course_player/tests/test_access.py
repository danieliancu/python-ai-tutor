from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.course_player.tests.helpers import PlayerFixtures, player_url
from apps.curriculum.tests.helpers import make_world
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile


class PlayerAccessTests(PlayerFixtures, TestCase):
    def progress_url(self, world=None):
        return reverse("course_player:progress", args=[(world or self.python_world).pk])

    def test_anonymous_is_sent_to_login(self) -> None:
        anonymous = Client()
        for url in (player_url(self.python_world), self.progress_url()):
            with self.subTest(url=url):
                response = anonymous.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_own_active_and_completed_enrollments(self) -> None:
        self.assertEqual(self.open().status_code, 200)
        self.assertEqual(self.client.get(self.progress_url()).status_code, 200)
        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        self.assertEqual(self.open().status_code, 200)

    def test_paused_and_missing_enrollments_are_forbidden(self) -> None:
        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        self.assertEqual(self.open().status_code, 403)
        self.assertEqual(self.client.get(self.progress_url()).status_code, 403)

        stranger = Client()
        stranger.force_login(make_user("stranger"))
        self.assertEqual(self.open(client=stranger).status_code, 403)

        other_world = make_world("Other World")
        self.assertEqual(self.open(world=other_world).status_code, 403)

    def test_other_learners_cannot_use_this_enrollment(self) -> None:
        other = make_user("other")
        LearnerProfile.objects.create(user=other)
        client = Client()
        client.force_login(other)
        self.assertEqual(self.open(client=client).status_code, 403)
        # There is no enrollment id in the URL to tamper with.
        self.assertEqual(
            client.get(
                player_url(self.python_world) + f"?enrollment={self.enrollment.pk}"
            ).status_code,
            403,
        )

    def test_unknown_or_unpublished_world(self) -> None:
        self.assertEqual(self.client.get("/learn/worlds/999999/").status_code, 404)
        self.python_world.is_published = False
        self.python_world.save()
        self.assertEqual(self.open().status_code, 404)

    def test_explicit_exercise_is_validated(self) -> None:
        self.assertEqual(self.open(self.gap).status_code, 200)
        self.assertEqual(self.open(self.translation).status_code, 404)  # another World
        self.gap.is_published = False
        self.gap.save()
        self.assertEqual(self.open(self.gap).status_code, 404)
        self.assertEqual(
            self.client.get(player_url(self.python_world) + "?exercise=abc").status_code, 404
        )
        self.assertEqual(
            self.client.get(self.progress_url() + f"?exercise={self.translation.pk}").status_code,
            404,
        )
        # An explicit exercise never bypasses enrollment.
        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        self.assertEqual(self.open(self.mcq).status_code, 403)


class RootRedirectTests(PlayerFixtures, TestCase):
    def test_enrolled_learner_goes_to_their_course(self) -> None:
        response = self.client.get(reverse("home"))
        # The first active enrollment (fixtures enroll Python first).
        self.assertRedirects(response, player_url(self.python_world))

    def test_active_is_preferred_over_completed(self) -> None:
        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        self.assertRedirects(self.client.get(reverse("home")), player_url(self.english_world))

    def test_completed_is_used_when_nothing_is_active(self) -> None:
        Enrollment.objects.exclude(pk=self.enrollment.pk).update(status=EnrollmentStatus.PAUSED)
        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        self.assertRedirects(self.client.get(reverse("home")), player_url(self.python_world))

    def test_anonymous_still_gets_the_public_shell(self) -> None:
        response = Client().get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demo preview")
        self.assertNotContains(response, "course-player-config")
