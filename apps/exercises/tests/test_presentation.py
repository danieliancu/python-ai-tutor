import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.presentation import PUBLIC_FIELDS, exercise_presentation
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain

SECRET = "SECRET-ANSWER-7f3a"


class PresentationTests(TestCase):
    def setUp(self) -> None:
        self.exercise = make_exercise(
            make_lesson_chain(),
            title="Pick the loop keyword",
            slug="pick-loop-keyword",
            prompt="Which keyword starts a loop over a list?",
            instructions="Choose one option.",
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={"options": [{"id": "a", "text": "for"}, {"id": "b", "text": "if"}]},
            evaluation_spec={"correct_option": "a", "explanation": SECRET},
            target_seconds=30,
        )

    def test_contains_exactly_the_public_fields(self) -> None:
        data = exercise_presentation(self.exercise)
        self.assertEqual(tuple(data), PUBLIC_FIELDS)
        self.assertEqual(
            data,
            {
                "id": self.exercise.pk,
                "title": "Pick the loop keyword",
                "slug": "pick-loop-keyword",
                "prompt": "Which keyword starts a loop over a list?",
                "instructions": "Choose one option.",
                "response_type": "multiple_choice",
                "learning_mode": "recognise",
                "content": {"options": [{"id": "a", "text": "for"}, {"id": "b", "text": "if"}]},
                "target_seconds": 30,
            },
        )

    def test_evaluation_spec_is_never_included(self) -> None:
        data = exercise_presentation(Exercise.objects.get(pk=self.exercise.pk))
        self.assertNotIn("evaluation_spec", data)
        serialized = json.dumps(data)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("correct_option", serialized)
        self.assertNotIn("evaluation_spec", PUBLIC_FIELDS)

    def test_content_is_a_copy(self) -> None:
        data = exercise_presentation(self.exercise)
        data["content"]["options"].append({"id": "z", "text": "injected"})
        self.assertEqual(len(self.exercise.content["options"]), 2)

    def test_no_template_renders_the_evaluation_spec(self) -> None:
        template_dirs = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
        offenders = [
            path
            for directory in template_dirs
            for path in directory.rglob("*")
            if path.is_file() and "evaluation_spec" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])
