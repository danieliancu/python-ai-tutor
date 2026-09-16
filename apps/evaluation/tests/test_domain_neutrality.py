"""The same evaluators serve every subject. Test data only."""

import inspect

from django.test import TestCase

from apps.evaluation.engine import evaluate_exercise
from apps.evaluation.evaluators import fill_gap, multiple_choice, numeric, pending
from apps.evaluation.results import EvaluationStatus
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain


class DomainNeutralityTests(TestCase):
    def setUp(self) -> None:
        self.python_mcq = make_exercise(
            make_lesson_chain("Python Foundations"),
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "x > 10"}, {"id": "b", "text": "x >= 10"}]},
            evaluation_spec={"correct_option": "b"},
        )
        english = make_lesson_chain("English A1")
        self.english_mcq = make_exercise(
            english,
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "An"}, {"id": "b", "text": "A"}]},
            evaluation_spec={"correct_option": "a"},
        )
        self.english_gap = make_exercise(
            english,
            response_type=ResponseType.FILL_GAP,
            learning_mode=LearningMode.COMPLETE,
            content={"template": "She __ to school every day."},
            evaluation_spec={"accepted_answers": ["goes"], "case_sensitive": False},
        )
        self.maths_numeric = make_exercise(
            make_lesson_chain("Maths Foundations"),
            response_type=ResponseType.NUMERIC,
            learning_mode=LearningMode.CREATE,
            content={"unit": "cm²"},
            evaluation_spec={"expected": 28.27, "tolerance": 0.01},
        )

    def test_python_and_english_share_the_multiple_choice_evaluator(self) -> None:
        for exercise, right, wrong in ((self.python_mcq, "b", "a"), (self.english_mcq, "a", "b")):
            with self.subTest(world=exercise.lesson.concept.skill.world.title):
                correct = evaluate_exercise(exercise, right)
                self.assertEqual(correct.status, EvaluationStatus.CORRECT)
                self.assertEqual(correct.evaluator, "multiple_choice")
                self.assertEqual(
                    evaluate_exercise(exercise, wrong).status, EvaluationStatus.INCORRECT
                )

    def test_english_fill_gap(self) -> None:
        self.assertEqual(evaluate_exercise(self.english_gap, "Goes").status, "correct")
        self.assertEqual(evaluate_exercise(self.english_gap, "go").status, "incorrect")

    def test_maths_numeric(self) -> None:
        self.assertEqual(evaluate_exercise(self.maths_numeric, "28.275").status, "correct")
        self.assertEqual(evaluate_exercise(self.maths_numeric, 28.3).status, "incorrect")
        self.assertEqual(evaluate_exercise(self.maths_numeric, "about 28").status, "invalid")

    def test_evaluators_know_nothing_about_worlds(self) -> None:
        for module in (multiple_choice, fill_gap, numeric, pending):
            source = inspect.getsource(module)
            with self.subTest(module=module.__name__):
                for word in ("world", "World", "python-foundations", "lesson", "skill"):
                    self.assertNotIn(word, source)
