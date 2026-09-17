import json
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.attempts.tests.helpers import (
    SECRET_GAP,
    SECRET_NUMBER,
    SECRET_OPTION,
    SECRET_OUTPUT,
    SECRET_SOLUTION,
)
from apps.curriculum.tests.helpers import make_concept, make_skill
from apps.exercises.models import LearningMode
from apps.learner_intelligence.models import ConceptState
from apps.learner_intelligence.services import refresh_concept_state
from apps.learner_intelligence.tests.helpers import BASE_TIME, INCORRECT, IntelligenceFixtures
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile
from apps.python_runner.tests.fakes import outcome

FORBIDDEN_KEYS = {
    "submitted_answer",
    "answer",
    "correct_option",
    "accepted_answers",
    "expected",
    "expected_stdout",
    "reference_solution",
    "reference_answers",
    "tests",
    "evaluation_spec",
    "diagnostics",
    "mistakes",
    "container",
    "container_id",
    "image",
    "docker",
}
SUMMARY_KEYS = {
    "mastery",
    "concepts_total",
    "concepts_started",
    "weak",
    "learning",
    "practising",
    "mastered",
    "review_due",
    "active_misconceptions",
    "watch_misconceptions",
}
CONCEPT_KEYS = {
    "concept_id",
    "skill_id",
    "title",
    "mastery",
    "band",
    "retention",
    "independence",
    "fluency",
    "trend",
    "evidence_count",
    "correct_count",
    "stability_days",
    "last_attempt_at",
    "review_due_at",
    "review_due",
    "modes",
    "misconceptions",
}


def state_url(world_id: int) -> str:
    return reverse("learner_intelligence:learning_state", args=[world_id])


def all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(all_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(all_keys(v) for v in value))
    return set()


class LearningStateEndpointTests(IntelligenceFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def get(self, world=None, client=None):
        return (client or self.client).get(state_url((world or self.python_world).pk))

    def test_active_and_completed_enrollments_can_read(self) -> None:
        self.assertEqual(self.get().status_code, 200)
        self.enrollment.status = EnrollmentStatus.COMPLETED
        self.enrollment.save()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["world_id"], self.python_world.pk)

    def test_paused_enrollment_is_denied(self) -> None:
        self.enrollment.status = EnrollmentStatus.PAUSED
        self.enrollment.save()
        response = self.get()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "forbidden"})

    def test_without_enrollment_is_denied(self) -> None:
        other = make_user("other")
        LearnerProfile.objects.create(user=other)
        client = Client()
        client.force_login(other)
        self.assertEqual(self.get(client=client).status_code, 403)

    def test_anonymous_is_rejected(self) -> None:
        response = self.get(client=Client())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "authentication_required"})

    def test_unknown_or_unpublished_world_is_not_found(self) -> None:
        self.assertEqual(self.client.get(state_url(999_999)).status_code, 404)
        self.python_world.is_published = False
        self.python_world.save()
        self.assertEqual(self.get().status_code, 404)

    def test_state_cannot_be_written(self) -> None:
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    state_url(self.python_world.pk),
                    data=json.dumps({"mastery": 100, "band": "mastered"}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 405)
        self.assertFalse(ConceptState.objects.exists())

    def test_summary_counts_include_unstarted_concepts(self) -> None:
        skill = self.concept.skill
        unstarted = make_concept(skill)
        make_concept(skill, is_published=False)
        hidden_skill = make_skill(self.python_world, is_published=False)
        make_concept(hidden_skill)
        second_skill = make_skill(self.python_world)
        make_concept(second_skill)

        self.record(self.mcq, "opt-a")  # incorrect → weak, due now
        for _ in range(3):
            self.record(self.translation, "Hello")  # other world: must not appear

        data = self.get().json()
        self.assertEqual(set(data), {"world_id", "generated_at", "summary", "skills", "concepts"})
        self.assertEqual(set(data["summary"]), SUMMARY_KEYS)
        self.assertEqual(
            data["summary"],
            {
                "mastery": 0.0,
                "concepts_total": 3,
                "concepts_started": 1,
                "weak": 1,
                "learning": 0,
                "practising": 0,
                "mastered": 0,
                "review_due": 1,
                "active_misconceptions": 0,
                "watch_misconceptions": 0,
            },
        )
        self.assertEqual([s["skill_id"] for s in data["skills"]], [skill.pk, second_skill.pk])
        self.assertEqual(data["skills"][0]["concepts_total"], 2)
        self.assertNotIn("active_misconceptions", data["skills"][0])
        self.assertEqual(data["skills"][1]["concepts_started"], 0)

        concepts = {c["concept_id"]: c for c in data["concepts"]}
        self.assertEqual(len(concepts), 3)
        for concept in concepts.values():
            self.assertEqual(set(concept), CONCEPT_KEYS)
        started = concepts[self.concept.pk]
        self.assertEqual(started["band"], "weak")
        self.assertTrue(started["review_due"])
        self.assertEqual(started["modes"], {"recognise": 0.0})
        self.assertEqual(started["independence"], 0.0)
        idle = concepts[unstarted.pk]
        self.assertEqual(
            (idle["band"], idle["mastery"], idle["retention"], idle["modes"], idle["review_due"]),
            ("not_started", 0.0, None, {}, False),
        )

    def test_signals_and_modes_are_reported(self) -> None:
        day = timedelta(days=1)
        for index, mode in enumerate(LearningMode.values):
            self.make_attempt(self.by_mode[mode], at=BASE_TIME + index * day, duration_seconds=30)
        self.make_attempt(
            self.by_mode["fix"], INCORRECT, at=BASE_TIME + 5 * day, duration_seconds=30
        )
        self.make_attempt(self.by_mode["create"], at=BASE_TIME + 6 * day, duration_seconds=30)
        state = refresh_concept_state(self.enrollment, self.concept)
        concept = self.get().json()["concepts"][0]
        self.assertEqual(list(concept["modes"]), ["recognise", "complete", "fix", "create"])
        self.assertEqual(concept["mastery"], float(state.mastery_score))
        self.assertEqual(concept["trend"], "falling")  # 1,1,1 then 1,x,1
        self.assertIsNotNone(concept["retention"])
        self.assertIsNotNone(concept["fluency"])
        self.assertEqual(concept["review_due_at"], state.review_due_at.isoformat())

    def test_no_secrets_or_answers_are_exposed(self) -> None:
        self.use_python_backend(lambda *a: outcome(SECRET_OUTPUT + "\n"))
        self.record(self.mcq, SECRET_OPTION)
        self.record(self.gap, SECRET_GAP)
        self.record(self.code, f"print('{SECRET_OUTPUT}')")
        self.record(self.code, "print('nope')")
        self.record(self.gap, "wrong")

        for world in (self.python_world, self.maths_world):
            response = self.get(world)
            self.assertEqual(response.status_code, 200)
            body = response.content.decode()
            self.assertEqual(all_keys(response.json()) & FORBIDDEN_KEYS, set())
            for secret in (
                SECRET_OPTION,
                SECRET_GAP,
                str(SECRET_NUMBER),
                SECRET_OUTPUT,
                SECRET_SOLUTION,
                "nope",
                "wrong",
                "print(",
            ):
                self.assertNotIn(secret, body)

    def test_other_learners_state_is_not_visible(self) -> None:
        other = make_user("other")
        other_enrollment = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=other), world=self.python_world
        )
        self.make_attempt(self.by_mode["create"], enrollment=other_enrollment)
        refresh_concept_state(other_enrollment, self.concept)
        data = self.get().json()
        self.assertEqual(data["summary"]["concepts_started"], 0)
