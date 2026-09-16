import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain


class ExerciseAdminTests(TestCase):
    def setUp(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        self.lesson = make_lesson_chain("Python Foundations")
        self.exercise = make_exercise(self.lesson, title="Print big numbers")
        self.english = make_exercise(
            make_lesson_chain("English A1"),
            title="Translate a greeting",
            response_type=ResponseType.TRANSLATION,
            learning_mode=LearningMode.CREATE,
        )

    def result_count(self, params: dict) -> int:
        response = self.client.get(reverse("admin:exercises_exercise_changelist"), params)
        self.assertEqual(response.status_code, 200)
        return response.context["cl"].result_count

    def test_pages_render(self) -> None:
        for url in (
            reverse("admin:exercises_exercise_changelist"),
            reverse("admin:exercises_exercise_add"),
            reverse("admin:exercises_exercise_change", args=[self.exercise.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_filters_and_search(self) -> None:
        self.assertEqual(self.result_count({"response_type__exact": "translation"}), 1)
        self.assertEqual(self.result_count({"learning_mode__exact": "complete"}), 1)
        world = self.lesson.concept.skill.world
        self.assertEqual(
            self.result_count({"lesson__concept__skill__world__id__exact": world.pk}), 1
        )
        self.assertEqual(self.result_count({"q": "greeting"}), 1)
        self.assertEqual(self.result_count({"q": self.lesson.title}), 1)

    def test_lesson_page_lists_its_exercises_read_only(self) -> None:
        response = self.client.get(reverse("admin:curriculum_lesson_change", args=[self.lesson.pk]))
        self.assertContains(response, "Print big numbers")
        self.assertContains(
            response, reverse("admin:exercises_exercise_change", args=[self.exercise.pk])
        )
        inline = next(
            formset
            for formset in response.context["inline_admin_formsets"]
            if formset.opts.model is Exercise
        )
        self.assertFalse(inline.has_add_permission)
        self.assertNotContains(response, 'name="exercises-0-title"')

    def post_exercise(self, content: dict):
        return self.client.post(
            reverse("admin:exercises_exercise_add"),
            {
                "lesson": self.lesson.pk,
                "title": "Pick a keyword",
                "slug": "pick-a-keyword",
                "order": 9,
                "response_type": ResponseType.MULTIPLE_CHOICE,
                "learning_mode": LearningMode.RECOGNISE,
                "prompt": "Which keyword starts a loop?",
                "instructions": "",
                "content": json.dumps(content),
                "evaluation_spec": json.dumps({"correct_option": "a"}),
                "target_seconds": "",
            },
        )

    def test_admin_form_rejects_leaked_answers(self) -> None:
        response = self.post_exercise(
            {"options": [{"id": "a", "text": "for", "correct": True}, {"id": "b", "text": "if"}]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must not say whether it is correct")
        self.assertFalse(Exercise.objects.filter(slug="pick-a-keyword").exists())

    def test_admin_form_creates_a_valid_exercise(self) -> None:
        response = self.post_exercise(
            {"options": [{"id": "a", "text": "for"}, {"id": "b", "text": "if"}]}
        )
        self.assertEqual(response.status_code, 302)
        exercise = Exercise.objects.get(slug="pick-a-keyword")
        self.assertEqual(exercise.evaluation_spec, {"correct_option": "a"})
