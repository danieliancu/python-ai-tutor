import json
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.tests.helpers import ENABLED, TutorFixtures
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile

TURN_KEYS = {
    "id",
    "intent",
    "response_kind",
    "reply",
    "should_retry",
    "exercise_id",
    "attempt_id",
    "assistance",
    "created_at",
}
HISTORY_KEYS = {
    "id",
    "intent",
    "response_kind",
    "user_message",
    "reply",
    "exercise_id",
    "attempt_id",
    "created_at",
}


def url(world) -> str:
    return reverse("ai_tutor:turns", args=[world.pk])


class TutorEndpointTests(TutorFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        patcher = mock.patch("apps.ai_tutor.services.get_provider", return_value=self.provider)
        self.get_provider = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, body, client=None, world=None):
        return (client or self.client).post(
            url(world or self.python_world),
            data=body if isinstance(body, str) else json.dumps(body),
            content_type="application/json",
        )

    def test_post_hint(self) -> None:
        response = self.post({"intent": "hint", "exercise_id": self.mcq.pk})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(set(data), TURN_KEYS)
        self.assertEqual(
            (data["intent"], data["response_kind"], data["exercise_id"]),
            ("hint", "hint", self.mcq.pk),
        )
        self.assertEqual(
            data["assistance"],
            {"hint_level": 1, "used_explanation": False, "used_solution": False},
        )
        self.assertTrue(data["should_retry"])
        self.assertEqual(data["reply"], "Let's look at this together. (hint)")

    def test_post_ask_and_next_step(self) -> None:
        response = self.post({"message": "What is a loop?"})
        self.assertEqual((response.status_code, response.json()["intent"]), (201, "ask"))
        response = self.post({"intent": "next_step"})
        self.assertEqual(response.json()["response_kind"], "next_step")

    def test_history(self) -> None:
        for index in range(3):
            self.post({"message": f"question {index}"})
        self.old_turn(seconds_ago=1, status="failed", user_message="failed one")
        other = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=make_user("other")),
            world=self.python_world,
        )
        self.old_turn(other, user_message="not yours")
        self.old_turn(self.english_enrollment, user_message="other world")

        data = self.client.get(url(self.python_world)).json()
        self.assertEqual(
            [t["user_message"] for t in data["turns"]], [f"question {i}" for i in range(3)]
        )
        self.assertEqual(set(data["turns"][0]), HISTORY_KEYS)
        limited = self.client.get(url(self.python_world), {"limit": 2}).json()
        self.assertEqual(
            [t["user_message"] for t in limited["turns"]], ["question 1", "question 2"]
        )
        for bad in ("0", "-1", "abc"):
            with self.subTest(limit=bad):
                response = self.client.get(url(self.python_world), {"limit": bad})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(
            len(self.client.get(url(self.python_world), {"limit": 999}).json()["turns"]), 3
        )

    def test_history_is_capped(self) -> None:
        for index in range(55):
            self.old_turn(seconds_ago=1000 + index, user_message=str(index))
        turns = self.client.get(url(self.python_world), {"limit": 500}).json()["turns"]
        self.assertEqual(len(turns), 50)
        self.assertEqual(turns[-1]["user_message"], "0")
        self.assertEqual(len(self.client.get(url(self.python_world)).json()["turns"]), 20)

    def test_access(self) -> None:
        anonymous = Client()
        self.assertEqual(anonymous.get(url(self.python_world)).status_code, 401)
        self.assertEqual(self.post({"message": "hi"}, client=anonymous).status_code, 401)

        stranger = Client()
        stranger.force_login(make_user("stranger"))
        self.assertEqual(stranger.get(url(self.python_world)).status_code, 403)
        self.assertEqual(self.post({"message": "hi"}, client=stranger).status_code, 403)

        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        self.assertEqual(self.client.get(url(self.python_world)).status_code, 403)
        self.assertEqual(self.post({"message": "hi"}).status_code, 403)

        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        self.assertEqual(self.client.get(url(self.python_world)).status_code, 200)
        self.assertEqual(self.post({"message": "hi"}).status_code, 201)

        self.assertEqual(
            self.client.get(reverse("ai_tutor:turns", args=[999_999])).status_code, 404
        )
        self.python_world.is_published = False
        self.python_world.save()
        self.assertEqual(self.client.get(url(self.python_world)).status_code, 404)

    def test_exercise_from_another_world_is_forbidden(self) -> None:
        response = self.post({"intent": "hint", "exercise_id": self.translation.pk})
        self.assertEqual((response.status_code, response.json()), (403, {"error": "forbidden"}))
        response = self.post(
            {"intent": "hint", "exercise_id": self.mcq.pk}, world=self.english_world
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_is_enforced(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.post({"message": "hi"}, client=client)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TutorTurn.objects.exists())

    def test_invalid_bodies(self) -> None:
        cases = [
            ("not json", "malformed_json"),
            ("[1]", "body_must_be_an_object"),
            ({"message": "hi", "mastery": 100}, "unknown_fields"),
            ({"intent": "hint", "exercise_id": "12"}, "invalid_exercise_id"),
            ({"intent": "hint", "exercise_id": True}, "invalid_exercise_id"),
            ({"intent": "cheat"}, "invalid_intent"),
            ({"intent": "ask"}, "message_required"),
            ({"message": "x" * 4001}, "message_too_long"),
            ({"message": ["list"]}, "invalid_message"),
        ]
        for body, code in cases:
            with self.subTest(code=code):
                response = self.post(body)
                self.assertEqual((response.status_code, response.json()["error"]), (400, code))
        self.assertFalse(TutorTurn.objects.exists())

    def test_disabled_tutor(self) -> None:
        with override_settings(AI_TUTOR={**ENABLED, "ENABLED": False}):
            response = self.post({"message": "hi"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json(),
                {"error": "tutor_unavailable", "message": "The tutor is temporarily unavailable."},
            )
            self.assertEqual(self.client.get(url(self.python_world)).status_code, 200)
        self.get_provider.assert_not_called()

    def test_rate_limit(self) -> None:
        for _ in range(20):
            self.old_turn(seconds_ago=10)
        response = self.post({"message": "hi"})
        self.assertEqual((response.status_code, response.json()), (429, {"error": "rate_limited"}))

    def test_only_get_and_post(self) -> None:
        for method in ("put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(
                    getattr(self.client, method)(url(self.python_world)).status_code, 405
                )
