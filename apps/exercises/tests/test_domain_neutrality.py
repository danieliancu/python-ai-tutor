"""The same engine carries Python, English and Maths content. Test data only."""

from django.test import TestCase

from apps.accounts.tests.helpers import make_user
from apps.exercises.access import accessible_exercises
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.presentation import exercise_presentation
from apps.exercises.selectors import published_exercises
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, LearnerProfile


class DomainNeutralityTests(TestCase):
    def setUp(self) -> None:
        self.python = make_exercise(
            make_lesson_chain("Python Foundations"),
            title="Fix the loop condition",
            prompt="Print only numbers greater than 10.",
            response_type=ResponseType.CODE,
            learning_mode=LearningMode.FIX,
            content={
                "language": "python",
                "starter_code": "for n in numbers:\n    if n < 10:\n        print(n)\n",
            },
            evaluation_spec={"tests": [{"stdin": "", "expected_stdout": "12\n15\n"}]},
        )
        self.english = make_exercise(
            make_lesson_chain("English A1"),
            title="Translate a greeting",
            prompt="Translate into British English.",
            response_type=ResponseType.TRANSLATION,
            learning_mode=LearningMode.CREATE,
            content={
                "source_language": "ro",
                "target_language": "en-GB",
                "source_text": "Bună dimineața!",
            },
            evaluation_spec={"reference_answers": ["Good morning!"]},
        )
        self.maths = make_exercise(
            make_lesson_chain("Maths Foundations"),
            title="Simplify the expression",
            prompt="Simplify 2x + 3x.",
            response_type=ResponseType.MATH_EXPRESSION,
            learning_mode=LearningMode.CREATE,
            content={"notation": "plain"},
            evaluation_spec={"equivalent_to": "5*x"},
        )
        self.grammar = make_exercise(
            self.english.lesson,
            title="Choose the article",
            prompt="___ apple a day.",
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "An"}, {"id": "b", "text": "A"}]},
            evaluation_spec={"correct_option": "a"},
        )
        self.exercises = [self.python, self.english, self.maths, self.grammar]

    def test_all_subjects_share_one_model(self) -> None:
        self.assertEqual(Exercise.objects.count(), 4)
        self.assertEqual(
            {(e.response_type, e.learning_mode) for e in Exercise.objects.all()},
            {
                ("code", "fix"),
                ("translation", "create"),
                ("math_expression", "create"),
                ("multiple_choice", "recognise"),
            },
        )
        worlds = set(
            Exercise.objects.values_list("lesson__concept__skill__world__title", flat=True)
        )
        self.assertEqual(worlds, {"Python Foundations", "English A1", "Maths Foundations"})

    def test_each_subject_validates_and_presents_the_same_way(self) -> None:
        for exercise in self.exercises:
            with self.subTest(exercise=exercise.title):
                exercise.full_clean()
                data = exercise_presentation(exercise)
                self.assertEqual(data["content"], exercise.content)
                self.assertNotIn("evaluation_spec", data)
                for private_key in exercise.evaluation_spec:
                    self.assertNotIn(private_key, data)
                    self.assertNotIn(private_key, data["content"])

    def test_publication_and_access_work_across_subjects(self) -> None:
        self.assertEqual(set(published_exercises()), set(self.exercises))
        learner = LearnerProfile.objects.create(user=make_user("polyglot"))
        for exercise in (self.english, self.maths):
            Enrollment.objects.create(learner=learner, world=exercise.lesson.concept.skill.world)
        self.assertEqual(
            set(accessible_exercises(learner.user)), {self.english, self.grammar, self.maths}
        )

    def test_model_has_no_subject_specific_fields(self) -> None:
        names = {field.name for field in Exercise._meta.get_fields()}
        self.assertEqual(
            names,
            {
                "id",
                "lesson",
                "title",
                "slug",
                "prompt",
                "instructions",
                "order",
                "response_type",
                "learning_mode",
                "content",
                "evaluation_spec",
                "target_seconds",
                "is_published",
            },
        )
