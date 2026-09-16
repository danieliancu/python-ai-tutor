from pathlib import Path

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase

from apps.accounts.tests.helpers import make_user
from apps.evaluation.engine import evaluate_exercise, evaluate_for_learner
from apps.evaluation.evaluators.fill_gap import FillGapEvaluator
from apps.evaluation.evaluators.multiple_choice import MultipleChoiceEvaluator
from apps.evaluation.evaluators.numeric import NumericEvaluator
from apps.evaluation.evaluators.pending import DeferredTextEvaluator, UnsupportedEvaluator
from apps.evaluation.exceptions import (
    PUBLIC_UNAVAILABLE_MESSAGE,
    EvaluationConfigurationError,
    EvaluationUnavailable,
)
from apps.evaluation.registry import EVALUATORS, get_evaluator
from apps.evaluation.results import EvaluationStatus
from apps.evaluation.tests import helpers
from apps.exercises.models import Exercise, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, LearnerProfile


class RegistryTests(SimpleTestCase):
    def test_every_response_type_has_an_evaluator(self) -> None:
        self.assertEqual(set(EVALUATORS), set(ResponseType.values))

    def test_dispatch_by_response_type(self) -> None:
        expected = {
            ResponseType.MULTIPLE_CHOICE: MultipleChoiceEvaluator,
            ResponseType.FILL_GAP: FillGapEvaluator,
            ResponseType.NUMERIC: NumericEvaluator,
            ResponseType.TEXT: DeferredTextEvaluator,
            ResponseType.TRANSLATION: DeferredTextEvaluator,
            ResponseType.MATH_EXPRESSION: DeferredTextEvaluator,
            ResponseType.CODE: UnsupportedEvaluator,
            ResponseType.SPEAKING: UnsupportedEvaluator,
            ResponseType.LISTENING: UnsupportedEvaluator,
        }
        for response_type, evaluator_class in expected.items():
            with self.subTest(response_type=response_type):
                self.assertIsInstance(get_evaluator(response_type), evaluator_class)

    def test_engine_uses_the_matching_evaluator(self) -> None:
        self.assertEqual(evaluate_exercise(helpers.mcq(), "opt-b").evaluator, "multiple_choice")
        self.assertEqual(evaluate_exercise(helpers.fill_gap(), ">=").evaluator, "fill_gap")
        self.assertEqual(evaluate_exercise(helpers.numeric(), "12.5").evaluator, "numeric")

    def test_unknown_response_type_is_unsupported(self) -> None:
        result = evaluate_exercise(helpers.exercise("essay"), "anything")
        self.assertEqual(result.status, EvaluationStatus.UNSUPPORTED)
        self.assertIsNone(result.is_correct)
        self.assertEqual(result.diagnostics["reason"], "no_evaluator")

    def test_configuration_errors_are_not_wrong_answers(self) -> None:
        broken = helpers.mcq(correct=None)
        with self.assertRaises(EvaluationConfigurationError) as ctx:
            evaluate_exercise(broken, "opt-b")
        self.assertEqual(ctx.exception.exercise_id, broken.pk)
        self.assertIn("correct_option", ctx.exception.problem)
        self.assertEqual(ctx.exception.public_message, PUBLIC_UNAVAILABLE_MESSAGE)
        # A learner's malformed answer, by contrast, is a normal INVALID result.
        self.assertEqual(evaluate_exercise(helpers.mcq(), "opt-z").status, EvaluationStatus.INVALID)

    def test_evaluation_package_never_executes_code(self) -> None:
        package = Path(__file__).resolve().parent.parent
        banned = ("exec(", "eval(", "compile(", "subprocess", "os.system", "importlib", "openai")
        for path in package.rglob("*.py"):
            if "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for word in banned:
                with self.subTest(file=path.name, word=word):
                    self.assertNotIn(word, source)


class EngineDatabaseTests(TestCase):
    def setUp(self) -> None:
        self.lesson = make_lesson_chain("Maths Foundations")
        self.exercise = make_exercise(
            self.lesson,
            response_type=ResponseType.NUMERIC,
            content={"unit": "cm"},
            evaluation_spec={"expected": 12.5, "tolerance": 0.1},
        )
        self.user = make_user("learner")

    def test_evaluation_needs_no_queries(self) -> None:
        exercise = Exercise.objects.get(pk=self.exercise.pk)
        with self.assertNumQueries(0):
            result = evaluate_exercise(exercise, "12.45")
        self.assertEqual(result.status, EvaluationStatus.CORRECT)

    def test_evaluation_stores_nothing(self) -> None:
        from django.apps import apps

        counts = {model: model.objects.count() for model in apps.get_models()}
        evaluate_exercise(self.exercise, "3")
        self.assertEqual(counts, {model: model.objects.count() for model in apps.get_models()})

    def enroll(self) -> None:
        profile = LearnerProfile.objects.create(user=self.user)
        Enrollment.objects.create(learner=profile, world=self.lesson.concept.skill.world)

    def test_learner_evaluation_requires_access(self) -> None:
        with self.assertRaises(PermissionDenied):
            evaluate_for_learner(AnonymousUser(), self.exercise, "12.5")
        with self.assertRaises(PermissionDenied):
            evaluate_for_learner(self.user, self.exercise, "12.5")

    def test_learner_gets_only_the_safe_presentation(self) -> None:
        self.enroll()
        self.assertEqual(
            evaluate_for_learner(self.user, self.exercise, "12.5"),
            {"status": "correct", "score": 1.0, "is_correct": True, "message": "Correct."},
        )

    def test_misconfiguration_is_hidden_from_learners(self) -> None:
        self.enroll()
        Exercise.objects.filter(pk=self.exercise.pk).update(evaluation_spec={"expected": "x"})
        self.exercise.refresh_from_db()
        with (
            self.assertLogs("apps.evaluation.engine", level="ERROR") as logs,
            self.assertRaises(EvaluationUnavailable) as ctx,
        ):
            evaluate_for_learner(self.user, self.exercise, "12.5")
        self.assertEqual(str(ctx.exception), PUBLIC_UNAVAILABLE_MESSAGE)
        self.assertNotIn("expected", ctx.exception.public_message)
        self.assertIn("expected", logs.output[0])
