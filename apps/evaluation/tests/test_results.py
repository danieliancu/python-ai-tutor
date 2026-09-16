import dataclasses

from django.test import SimpleTestCase

from apps.evaluation import results
from apps.evaluation.presentation import PUBLIC_FIELDS, evaluation_result_presentation
from apps.evaluation.results import EvaluationResult, EvaluationStatus


class EvaluationResultTests(SimpleTestCase):
    def test_statuses_have_stable_values(self) -> None:
        self.assertEqual(
            [status.value for status in EvaluationStatus],
            ["correct", "incorrect", "invalid", "review_required", "unsupported"],
        )

    def test_constructors(self) -> None:
        cases = [
            (results.correct("x"), "correct", 1.0, True),
            (results.incorrect("x", "wrong"), "incorrect", 0.0, False),
            (results.invalid("x", "bad"), "invalid", None, None),
            (results.review_required("x", "later"), "review_required", None, None),
            (results.unsupported("x", "none"), "unsupported", None, None),
        ]
        for result, status, score, is_correct in cases:
            with self.subTest(status=status):
                self.assertEqual(result.status, status)
                self.assertEqual(result.score, score)
                self.assertIs(result.is_correct, is_correct)
                self.assertEqual(result.evaluator, "x")
                self.assertTrue(result.message)
        self.assertEqual(dict(results.incorrect("x", "wrong").diagnostics), {"reason": "wrong"})
        self.assertEqual(dict(results.correct("x").diagnostics), {})

    def test_result_is_immutable(self) -> None:
        result = results.incorrect("x", "wrong")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.score = 1.0
        with self.assertRaises(TypeError):
            result.diagnostics["reason"] = "changed"

    def test_diagnostics_are_copied(self) -> None:
        source = {"reason": "wrong"}
        result = EvaluationResult("incorrect", "x", "m", 0.0, False, source)
        source["reason"] = "tampered"
        self.assertEqual(result.diagnostics["reason"], "wrong")

    def test_invariants(self) -> None:
        for kwargs in (
            {"status": "correct", "score": None, "is_correct": True},
            {"status": "correct", "score": 1.0, "is_correct": False},
            {"status": "incorrect", "score": 1.5, "is_correct": False},
            {"status": "incorrect", "score": -0.1, "is_correct": False},
            {"status": "invalid", "score": 0.0, "is_correct": None},
            {"status": "review_required", "score": None, "is_correct": False},
            {"status": "unknown", "score": None, "is_correct": None},
        ):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                EvaluationResult(evaluator="x", message="m", **kwargs)

    def test_partial_scores_are_representable(self) -> None:
        result = EvaluationResult("incorrect", "future", "m", score=0.5, is_correct=False)
        self.assertEqual(result.score, 0.5)

    def test_presentation_is_an_allow_list(self) -> None:
        data = evaluation_result_presentation(results.incorrect("secret-evaluator", "wrong"))
        self.assertEqual(tuple(data), PUBLIC_FIELDS)
        self.assertEqual(
            data,
            {
                "status": "incorrect",
                "score": 0.0,
                "is_correct": False,
                "message": "That answer isn't correct yet.",
            },
        )
        self.assertIsInstance(data["status"], str)
