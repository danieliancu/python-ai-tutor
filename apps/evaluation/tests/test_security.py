"""Nothing a learner can see may reveal how the exercise is judged."""

import json

from django.test import SimpleTestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.presentation import evaluation_result_presentation
from apps.evaluation.tests import helpers

FORBIDDEN_KEYS = (
    "correct_option",
    "accepted_answers",
    "expected",
    "tolerance",
    "reference_solution",
    "tests",
    "expected_stdout",
    "evaluation_spec",
    "criteria",
)

MCQ_SECRET = "secret-option-9"
GAP_SECRET = "gap-secret-value"
NUMERIC_SECRET = 4242.42


def cases():
    mcq = helpers.mcq(correct=MCQ_SECRET, options=("decoy-1", MCQ_SECRET, "decoy-2"))
    gap = helpers.fill_gap(answers=(GAP_SECRET,), case_sensitive=True)
    numeric = helpers.numeric(NUMERIC_SECRET, tolerance=0.37)
    return [
        ("mcq-correct", mcq, MCQ_SECRET, ()),
        ("mcq-incorrect", mcq, "decoy-1", (MCQ_SECRET,)),
        ("mcq-invalid", mcq, "nope", (MCQ_SECRET,)),
        ("gap-correct", gap, GAP_SECRET, ()),
        ("gap-incorrect", gap, "wrong", (GAP_SECRET,)),
        ("gap-case", gap, GAP_SECRET.upper(), (GAP_SECRET,)),
        ("gap-invalid", gap, "", (GAP_SECRET,)),
        ("numeric-correct", numeric, "4242.5", ("4242.42", "0.37")),
        ("numeric-incorrect", numeric, "1", ("4242", "0.37")),
        ("numeric-invalid", numeric, "abc", ("4242", "0.37")),
    ]


class LeakageTests(SimpleTestCase):
    def test_learner_payload_contains_no_evaluation_details(self) -> None:
        for name, exercise, answer, secrets in cases():
            result = evaluate_exercise(exercise, answer)
            payload = json.dumps(evaluation_result_presentation(result))
            with self.subTest(case=name):
                self.assertEqual(
                    set(json.loads(payload)), {"status", "score", "is_correct", "message"}
                )
                for key in FORBIDDEN_KEYS:
                    self.assertNotIn(key, payload)
                for secret in secrets:
                    self.assertNotIn(secret, payload.casefold())

    def test_full_internal_result_contains_no_answers_either(self) -> None:
        for name, exercise, answer, secrets in cases():
            text = repr(evaluate_exercise(exercise, answer)).casefold()
            with self.subTest(case=name):
                for key in FORBIDDEN_KEYS:
                    self.assertNotIn(key, text)
                for secret in secrets:
                    self.assertNotIn(secret.casefold(), text)

    def test_diagnostics_only_hold_reason_codes(self) -> None:
        for name, exercise, answer, _ in cases():
            diagnostics = evaluate_exercise(exercise, answer).diagnostics
            with self.subTest(case=name):
                self.assertLessEqual(set(diagnostics), {"reason"})
                for value in diagnostics.values():
                    self.assertRegex(value, r"^[a-z_]+$")
