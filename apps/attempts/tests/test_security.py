"""Nothing hidden about an exercise may be stored with attempts or returned to learners."""

import json

from django.core import serializers
from django.test import TestCase
from django.urls import reverse

from apps.attempts.models import AttemptMistake, ExerciseAttempt
from apps.attempts.tests.helpers import (
    SECRET_GAP,
    SECRET_NUMBER,
    SECRET_OPTION,
    SECRET_OUTPUT,
    SECRET_SOLUTION,
    AttemptFixtures,
)
from apps.python_runner.tests.fakes import outcome

FORBIDDEN = (
    "correct_option",
    "accepted_answers",
    "expected",
    "tolerance",
    "expected_stdout",
    "tests",
    "reference_solution",
    "evaluation_spec",
    "docker",
    "pyrun-",
    "container",
    "/sandbox",
    "/tmp",
    "C:\\\\",
    SECRET_OUTPUT,
    SECRET_SOLUTION,
    str(SECRET_NUMBER),
)


class AttemptSecurityTests(AttemptFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.backend = self.use_python_backend(
            lambda *a: outcome(stderr='File "/sandbox/learner.py"\nNameError: x', exit_code=1)
        )
        self.responses = []
        for exercise, answer in (
            (self.mcq, "opt-a"),
            (self.mcq, "nope"),
            (self.gap, "wrong"),
            (self.gap, SECRET_GAP.upper()),
            (self.numeric, "1"),
            (self.numeric, "not a number"),
            (self.code, "print(x)"),
            (self.translation, "Hi"),
        ):
            self.responses.append(
                self.client.post(
                    reverse("attempts:exercise_attempts", args=[exercise.pk]),
                    data=json.dumps({"answer": answer}),
                    content_type="application/json",
                )
            )

    def assert_clean(self, text: str, label: str) -> None:
        for word in (*FORBIDDEN, SECRET_OPTION, SECRET_GAP):
            with self.subTest(source=label, word=word):
                self.assertNotIn(word, text)

    def test_stored_rows_hold_no_hidden_data(self) -> None:
        self.assertEqual(ExerciseAttempt.objects.count(), 8)
        stored = serializers.serialize(
            "json",
            [*ExerciseAttempt.objects.all(), *AttemptMistake.objects.all()],
            fields=[
                "status",
                "score",
                "is_correct",
                "evaluator",
                "message",
                "diagnostics",
                "code",
                "details",
            ],
        )
        self.assert_clean(stored, "database")
        runtime = AttemptMistake.objects.get(code="runtime_error")
        self.assertEqual(runtime.details, {"error_type": "NameError"})

    def test_learner_answers_are_the_only_submitted_data_stored(self) -> None:
        answers = set(ExerciseAttempt.objects.values_list("submitted_answer", flat=True))
        self.assertEqual(
            answers,
            {"opt-a", "nope", "wrong", SECRET_GAP.upper(), "1", "not a number", "print(x)", "Hi"},
        )

    def test_json_responses_hold_no_hidden_data(self) -> None:
        for response in self.responses:
            self.assertEqual(response.status_code, 201)
            body = response.json()
            body.pop("submitted_answer")
            self.assert_clean(json.dumps(body), "submit")

        listing = self.client.get(reverse("attempts:exercise_attempts", args=[self.code.pk]))
        self.assert_clean(listing.content.decode(), "list")
        for attempt in ExerciseAttempt.objects.exclude(submitted_answer__in=[SECRET_GAP.upper()]):
            detail = self.client.get(reverse("attempts:attempt_detail", args=[attempt.pk]))
            self.assert_clean(detail.content.decode(), f"detail {attempt.pk}")

    def test_containers_only_saw_the_learner_answer(self) -> None:
        self.assertEqual(len(self.backend.requests), 1)
        request = self.backend.requests[0]
        self.assertEqual(request["files"], {"learner.py": "print(x)"})
        self.assertEqual(request["stdin"], "")
        self.assertEqual(request["argv"], ["/sandbox/learner.py"])
