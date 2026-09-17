import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.curriculum.tests.helpers import make_world
from apps.exercises.models import LearningMode
from apps.learners.models import EnrollmentStatus
from apps.next_action.tests.helpers import WorldFixtures

FORBIDDEN_KEYS = {
    "evaluation_spec",
    "correct_option",
    "accepted_answers",
    "expected",
    "expected_stdout",
    "reference_solution",
    "tests",
    "submitted_answer",
    "answer",
    "misconceptions_tags",
    "evidence",
    "source",
    "details",
    "priority_tier",
    "urgency_score",
    "urgency",
    "docker",
    "container",
}
DECISION_KEYS = {
    "algorithm_version",
    "action",
    "primary_reason",
    "reason_codes",
    "world_id",
    "skill",
    "concept",
    "lesson",
    "exercise",
    "target_learning_mode",
    "misconceptions",
    "generated_at",
}
SECRET_OPTION = "opt-SECRET-choice"
SECRET_SOLUTION = "SECRET-REFERENCE-SOLUTION"


def url(world_id: int) -> str:
    return reverse("next_action:next_action", args=[world_id])


def keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(v) for v in value))
    return set()


class NextActionEndpointTests(WorldFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def get(self, client=None, world=None):
        return (client or self.client).get(url((world or self.world).pk))

    def test_owner_with_active_or_completed_enrollment(self) -> None:
        response = self.get()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), DECISION_KEYS)
        self.assertEqual(data["action"], "learn")
        self.assertEqual(data["concept"], {"id": self.a1.pk, "title": self.a1.title})
        self.assertEqual(data["skill"], {"id": self.skill_a.pk, "title": self.skill_a.title})
        lesson = self.lessons[self.a1.pk]
        self.assertEqual(data["lesson"], {"id": lesson.pk, "title": lesson.title, "kind": "learn"})
        self.assertEqual(data["exercise"]["id"], self.ex[self.a1.pk].pk)
        self.assertEqual(data["target_learning_mode"], "recognise")
        self.assertEqual(data["reason_codes"], ["new_concept_ready"])
        self.assertEqual(data["misconceptions"], [])

        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        self.assertEqual(self.get().status_code, 200)

    def test_paused_or_missing_enrollment_is_forbidden(self) -> None:
        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        response = self.get()
        self.assertEqual((response.status_code, response.json()), (403, {"error": "forbidden"}))

        nobody = Client()
        nobody.force_login(make_user("nobody"))
        self.assertEqual(self.get(client=nobody).status_code, 403)

        elsewhere = self.other_learner("elsewhere", world=make_world("Another World"))
        client = Client()
        client.force_login(elsewhere.learner.user)
        self.assertEqual(self.get(client=client).status_code, 403)
        self.assertEqual(self.get(client=client, world=elsewhere.world).status_code, 200)

    def test_learners_only_see_their_own_decision(self) -> None:
        other = self.other_learner()
        self.misconception(self.a1, "off-by-one", enrollment=other)
        self.state(self.a1, 50.0, enrollment=other)
        client = Client()
        client.force_login(other.learner.user)
        self.assertEqual(self.get(client=client).json()["action"], "remediate")
        self.assertEqual(self.get().json()["action"], "learn")

    def test_anonymous_and_unknown_worlds(self) -> None:
        response = self.get(client=Client())
        self.assertEqual(
            (response.status_code, response.json()["error"]), (401, "authentication_required")
        )
        self.assertEqual(self.client.get(url(999_999)).status_code, 404)
        self.world.is_published = False
        self.world.save()
        self.assertEqual(self.get().status_code, 404)

    def test_read_only(self) -> None:
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    url(self.world.pk),
                    data=json.dumps({"action": "course_complete", "concept_id": self.b1.pk}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 405)

    def test_remediation_payload_is_safe(self) -> None:
        tagged = self.exercise(
            self.a1,
            LearningMode.FIX,
            tags=["off-by-one"],
            content={"options": [{"id": SECRET_OPTION, "text": "A"}, {"id": "b", "text": "B"}]},
            evaluation_spec={
                "correct_option": SECRET_OPTION,
                "explanation": SECRET_SOLUTION,
                "misconceptions": ["off-by-one", "hidden-tag"],
            },
        )
        self.state(self.a1, 50.0)
        self.misconception(self.a1, "off-by-one", confidence=72.4)
        self.attempt(tagged)
        data = self.get().json()
        self.assertEqual(data["action"], "remediate")
        self.assertEqual(data["exercise"]["id"], tagged.pk)
        self.assertEqual(
            data["misconceptions"],
            [
                {
                    "code": "off-by-one",
                    "title": "Off-by-one error",
                    "status": "active",
                    "confidence": 72.4,
                }
            ],
        )
        self.assertEqual(keys(data) & FORBIDDEN_KEYS, set())
        body = json.dumps(data)
        for secret in (SECRET_SOLUTION, "hidden-tag", "exercise_tag", "python_", "incorrect"):
            self.assertNotIn(secret, body)
        # The option id is learner-visible content (the question itself), never marked correct.
        self.assertNotIn("correct", json.dumps(data["exercise"]))

    def test_course_complete_payload(self) -> None:
        for concept in (self.a1, self.a2, self.b1):
            self.state(concept, 95.0, band="mastered", modes={"recognise": (95.0, 3)})
        data = self.get().json()
        self.assertEqual(data["action"], "course_complete")
        for key in ("skill", "concept", "lesson", "exercise", "target_learning_mode"):
            self.assertIsNone(data[key])

    def test_learning_state_endpoint_is_unchanged(self) -> None:
        response = self.client.get(
            reverse("learner_intelligence:learning_state", args=[self.world.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        response = self.client.get(
            reverse("learner_intelligence:learning_state", args=[self.world.pk])
        )
        self.assertEqual(response.status_code, 403)
