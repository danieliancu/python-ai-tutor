import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.attempts.models import ExerciseAttempt
from apps.attempts.tests.helpers import SECRET_OPTION, AttemptFixtures
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile

DETAIL_KEYS = {
    "id",
    "exercise_id",
    "attempt_number",
    "status",
    "score",
    "is_correct",
    "evaluator",
    "message",
    "diagnostics",
    "mistakes",
    "hint_level",
    "used_explanation",
    "used_solution",
    "duration_seconds",
    "submitted_at",
    "submitted_answer",
}


def attempts_url(exercise_id: int) -> str:
    return reverse("attempts:exercise_attempts", args=[exercise_id])


class AttemptEndpointTests(AttemptFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def post(self, exercise_id, body, client=None, raw=None):
        return (client or self.client).post(
            attempts_url(exercise_id),
            data=raw if raw is not None else json.dumps(body),
            content_type="application/json",
        )

    def test_anonymous_gets_401(self) -> None:
        anonymous = Client()
        self.assertEqual(self.post(self.mcq.pk, {"answer": "x"}, client=anonymous).status_code, 401)
        self.assertEqual(
            anonymous.get(attempts_url(self.mcq.pk)).json()["error"], "authentication_required"
        )
        attempt = self.record(self.mcq, "opt-a")
        self.assertEqual(
            anonymous.get(reverse("attempts:attempt_detail", args=[attempt.pk])).status_code, 401
        )
        self.assertEqual(ExerciseAttempt.objects.count(), 1)

    def test_submit_creates_attempt(self) -> None:
        response = self.post(
            self.mcq.pk,
            {
                "answer": "opt-a",
                "hint_level": 1,
                "used_explanation": False,
                "used_solution": False,
                "duration_seconds": 94,
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(set(data), DETAIL_KEYS)
        attempt = ExerciseAttempt.objects.get()
        self.assertEqual(
            {key: data[key] for key in DETAIL_KEYS - {"submitted_at"}},
            {
                "id": attempt.pk,
                "exercise_id": self.mcq.pk,
                "attempt_number": 1,
                "status": "incorrect",
                "score": 0.0,
                "is_correct": False,
                "evaluator": "multiple_choice",
                "message": "That answer isn't correct yet.",
                "diagnostics": {"reason": "wrong_option"},
                "mistakes": [{"code": "wrong_option", "details": {}}],
                "hint_level": 1,
                "used_explanation": False,
                "used_solution": False,
                "duration_seconds": 94,
                "submitted_answer": "opt-a",
            },
        )
        self.assertEqual(data["submitted_at"], attempt.submitted_at.isoformat())

    def test_optional_fields_default(self) -> None:
        data = self.post(self.mcq.pk, {"answer": SECRET_OPTION}).json()
        self.assertEqual((data["status"], data["hint_level"]), ("correct", 0))
        self.assertIsNone(data["duration_seconds"])
        self.assertEqual(data["mistakes"], [])
        self.assertEqual(self.post(self.mcq.pk, {"answer": None}).json()["status"], "invalid")

    def test_bad_requests(self) -> None:
        for raw, error in (
            ("{not json", "malformed_json"),
            ("", "malformed_json"),
            ('["answer"]', "body_must_be_an_object"),
            ('"answer"', "body_must_be_an_object"),
            ("{}", "answer_required"),
            ('{"answer": "x", "enrollment_id": 5}', "unknown_fields"),
            ('{"answer": "x", "hint_level": "high"}', "invalid_input"),
            ('{"answer": "x", "duration_seconds": -1}', "invalid_input"),
            ('{"answer": "x", "used_solution": "no"}', "invalid_input"),
        ):
            with self.subTest(raw=raw):
                response = self.post(self.mcq.pk, None, raw=raw)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"], error)
        fields = self.post(self.mcq.pk, {"answer": "x", "hint_level": 99}).json()["fields"]
        self.assertIn("hint_level", fields)
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_no_access_is_forbidden(self) -> None:
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status=EnrollmentStatus.PAUSED)
        response = self.post(self.mcq.pk, {"answer": "opt-a"})
        self.assertEqual((response.status_code, response.json()), (403, {"error": "forbidden"}))
        self.assertEqual(self.client.get(attempts_url(self.mcq.pk)).status_code, 403)
        outsider = Client()
        outsider.force_login(make_user("outsider"))
        self.assertEqual(
            self.post(self.numeric.pk, {"answer": "1"}, client=outsider).status_code, 403
        )
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_hidden_or_unknown_exercises_are_not_found(self) -> None:
        Exercise.objects.filter(pk=self.mcq.pk).update(is_published=False)
        self.assertEqual(self.post(self.mcq.pk, {"answer": "opt-a"}).status_code, 404)
        self.assertEqual(self.client.get(attempts_url(self.mcq.pk)).status_code, 404)
        self.assertEqual(self.post(999_999, {"answer": "opt-a"}).status_code, 404)

    def test_csrf_is_enforced(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.post(self.mcq.pk, {"answer": "opt-a"}, client=client)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ExerciseAttempt.objects.exists())

    def test_history_lists_only_own_attempts_newest_first(self) -> None:
        self.record(self.mcq, "opt-a")
        self.record(self.mcq, SECRET_OPTION)
        self.record(self.gap, "x")
        other = make_user("other")
        profile = LearnerProfile.objects.create(user=other)
        Enrollment.objects.create(learner=profile, world=self.python_world)
        self.record(self.mcq, "opt-a", user=other)

        data = self.client.get(attempts_url(self.mcq.pk)).json()
        self.assertEqual([a["attempt_number"] for a in data["attempts"]], [2, 1])
        self.assertEqual([a["status"] for a in data["attempts"]], ["correct", "incorrect"])
        for item in data["attempts"]:
            self.assertEqual(set(item), DETAIL_KEYS - {"submitted_answer"})

    def test_detail_is_owner_only(self) -> None:
        attempt = self.record(self.mcq, "opt-a")
        url = reverse("attempts:attempt_detail", args=[attempt.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submitted_answer"], "opt-a")
        self.assertEqual(set(response.json()), DETAIL_KEYS)

        other = Client()
        other_user = make_user("other")
        profile = LearnerProfile.objects.create(user=other_user)
        Enrollment.objects.create(learner=profile, world=self.python_world)
        other.force_login(other_user)
        self.assertEqual(other.get(url).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("attempts:attempt_detail", args=[999])).status_code, 404
        )

    def test_detail_follows_current_visibility(self) -> None:
        attempt = self.record(self.mcq, "opt-a")
        url = reverse("attempts:attempt_detail", args=[attempt.pk])
        Exercise.objects.filter(pk=self.mcq.pk).update(is_published=False)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(ExerciseAttempt.objects.filter(pk=attempt.pk).exists())

    def test_wrong_methods(self) -> None:
        self.assertEqual(self.client.put(attempts_url(self.mcq.pk)).status_code, 405)
        attempt = self.record(self.mcq, "opt-a")
        url = reverse("attempts:attempt_detail", args=[attempt.pk])
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
