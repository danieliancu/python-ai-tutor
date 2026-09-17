import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.attempts.tests.helpers import SECRET_OUTPUT, SECRET_SOLUTION
from apps.exercises.models import LearningMode
from apps.exercises.tests.helpers import make_exercise
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.tests.helpers import MisconceptionFixtures, fill_gap, python_code
from apps.python_runner.tests.fakes import outcome

FORBIDDEN = (
    "submitted_answer",
    "source",
    "correct_option",
    "accepted_answers",
    "expected",
    "expected_stdout",
    "tests",
    "reference_solution",
    "evaluation_spec",
    "docker",
    "container",
    "stdin",
    "stdout",
    "argv",
)
LEARNER_CODE = "while True:\n    print('LEARNER-PRIVATE-CODE')\n"
GAP_SECRET = "GAPSECRET"


def keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(v) for v in value))
    return set()


class MisconceptionSecurityTests(MisconceptionFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.runaway = make_exercise(
            self.mcq.lesson,
            learning_mode=LearningMode.FIX,
            **python_code(
                f"print('{SECRET_SOLUTION}')\n",
                ["infinite-while", "loop-condition"],
                tests=[{"stdin": "", "expected_stdout": SECRET_OUTPUT + "\n"}],
            ),
        )
        self.secret_gap = make_exercise(
            self.mcq.lesson, **fill_gap("x = __", [GAP_SECRET], ["off-by-one"])
        )
        self.use_python_backend(lambda *a: outcome(timed_out=True, exit_code=124))
        for _ in range(2):
            self.record(self.runaway, LEARNER_CODE)
            self.record(self.secret_gap, "wrong-guess")
        self.record(self.secret_gap, GAP_SECRET)

    def test_evidence_rows_hold_no_answers_or_specs(self) -> None:
        rows = list(MisconceptionEvidence.objects.values("code", "kind", "source", "details"))
        self.assertTrue(rows)
        text = json.dumps(rows, default=str)
        for secret in (
            SECRET_SOLUTION,
            SECRET_OUTPUT,
            GAP_SECRET,
            "LEARNER-PRIVATE-CODE",
            "wrong-guess",
            "print(",
        ):
            self.assertNotIn(secret, text)
        for row in rows:
            self.assertLessEqual(set(row["details"]), {"reason", "error_type", "pattern"})
        self.assertIn({"reason": "timeout"}, [row["details"] for row in rows])

    def test_student_state_holds_only_safe_misconception_fields(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("learner_intelligence:learning_state", args=[self.python_world.pk])
        )
        data = response.json()
        self.assertEqual(keys(data) & set(FORBIDDEN), set())
        body = response.content.decode()
        for secret in (
            SECRET_SOLUTION,
            SECRET_OUTPUT,
            GAP_SECRET,
            "LEARNER-PRIVATE-CODE",
            "wrong-guess",
            "exercise_tag",
            "python_",
        ):
            self.assertNotIn(secret, body)
        concept = data["concepts"][0]
        self.assertEqual(
            [(m["code"], m["status"]) for m in concept["misconceptions"]],
            [("infinite-while", "active"), ("loop-condition", "watch"), ("off-by-one", "watch")],
        )
        self.assertEqual(data["summary"]["active_misconceptions"], 1)
        self.assertEqual(data["summary"]["watch_misconceptions"], 2)

    def test_learning_state_cannot_write_misconceptions(self) -> None:
        self.client.force_login(self.user)
        url = reverse("learner_intelligence:learning_state", args=[self.python_world.pk])
        before = list(MisconceptionState.objects.values_list("code", "status"))
        response = self.client.post(
            url,
            data=json.dumps({"misconceptions": [{"code": "off-by-one", "status": "resolved"}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(list(MisconceptionState.objects.values_list("code", "status")), before)

    def test_admin_is_read_only_and_hides_answers(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        state = MisconceptionState.objects.first()
        evidence = MisconceptionEvidence.objects.first()
        for name, obj in (("misconceptionstate", state), ("misconceptionevidence", evidence)):
            with self.subTest(model=name):
                changelist = self.client.get(reverse(f"admin:misconceptions_{name}_changelist"))
                self.assertEqual(changelist.status_code, 200)
                change = self.client.get(
                    reverse(f"admin:misconceptions_{name}_change", args=[obj.pk])
                )
                self.assertEqual(change.status_code, 200)
                for page in (changelist, change):
                    body = page.content.decode()
                    for secret in (SECRET_SOLUTION, GAP_SECRET, "LEARNER-PRIVATE-CODE"):
                        self.assertNotIn(secret, body)
                add = self.client.get(reverse(f"admin:misconceptions_{name}_add"))
                self.assertEqual(add.status_code, 403)
                post = self.client.post(
                    reverse(f"admin:misconceptions_{name}_change", args=[obj.pk]), {}
                )
                self.assertEqual(post.status_code, 403)

    def test_admin_filters_and_search(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        url = reverse("admin:misconceptions_misconceptionstate_changelist")
        for params, count in (
            ({"status": "active"}, 1),
            ({"code": "off-by-one"}, 1),
            ({"enrollment__world__id__exact": self.python_world.pk}, 3),
            ({"enrollment__world__id__exact": self.english_world.pk}, 0),
            ({"q": "learner"}, 3),
            ({"q": "infinite"}, 1),
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).context["cl"].result_count, count)
