from django.test import TestCase

from apps.exercises.selectors import published_exercises, published_exercises_for_lesson
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain


class PublishedExercisesTests(TestCase):
    def setUp(self) -> None:
        self.lesson = make_lesson_chain()
        self.exercise = make_exercise(self.lesson)

    def test_fully_published_exercise_is_returned(self) -> None:
        self.assertEqual(list(published_exercises()), [self.exercise])

    def test_any_unpublished_level_hides_the_exercise(self) -> None:
        lesson = self.lesson
        levels = {
            "exercise": self.exercise,
            "lesson": lesson,
            "concept": lesson.concept,
            "skill": lesson.concept.skill,
            "world": lesson.concept.skill.world,
        }
        for name, obj in levels.items():
            with self.subTest(unpublished=name):
                type(obj).objects.filter(pk=obj.pk).update(is_published=False)
                self.assertFalse(published_exercises().exists())
                self.assertFalse(published_exercises_for_lesson(lesson).exists())
                type(obj).objects.filter(pk=obj.pk).update(is_published=True)
                self.assertTrue(published_exercises().exists())

    def test_lesson_selector_is_scoped_and_ordered(self) -> None:
        third = make_exercise(self.lesson, order=3)
        second = make_exercise(self.lesson, order=2)
        make_exercise(self.lesson, order=4, is_published=False)
        make_exercise(make_lesson_chain())
        self.assertEqual(
            list(published_exercises_for_lesson(self.lesson)), [self.exercise, second, third]
        )
