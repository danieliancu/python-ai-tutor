import copy
from itertools import count

from apps.curriculum.models import Lesson
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill, make_world
from apps.exercises.models import Exercise, LearningMode, ResponseType

_sequence = count(1)

CONTENT_EXAMPLES = {
    ResponseType.CODE: {"language": "python", "starter_code": "for number in numbers:\n    ..."},
    ResponseType.MULTIPLE_CHOICE: {
        "options": [{"id": "a", "text": "for"}, {"id": "b", "text": "loop"}]
    },
    ResponseType.FILL_GAP: {"template": "if age __ 18:"},
    ResponseType.TRANSLATION: {
        "source_language": "ro",
        "target_language": "en-GB",
        "source_text": "Bună dimineața!",
    },
    ResponseType.NUMERIC: {"unit": "cm"},
    ResponseType.MATH_EXPRESSION: {"notation": "plain"},
}


# Minimal valid evaluation specs for response types that have a contract.
SPEC_EXAMPLES = {
    ResponseType.CODE: {
        "strategy": "stdout",
        "tests": [{"stdin": "", "expected_stdout": "done\n"}],
    },
    ResponseType.MULTIPLE_CHOICE: {"correct_option": "a"},
    ResponseType.FILL_GAP: {"accepted_answers": [">="], "case_sensitive": True},
    ResponseType.NUMERIC: {"expected": 12.5, "tolerance": 0.1},
    ResponseType.TEXT: {"strategy": "rubric", "criteria": ["Answers the question."]},
}


def make_lesson_chain(world_title: str = "", **world_fields) -> Lesson:
    """A published World → Skill → Concept → Lesson chain; returns the Lesson."""
    world = make_world(world_title, **world_fields)
    return make_lesson(make_concept(make_skill(world)))


def make_exercise(lesson: Lesson, **fields) -> Exercise:
    n = next(_sequence)
    response_type = fields.setdefault("response_type", ResponseType.CODE)
    fields.setdefault("learning_mode", LearningMode.COMPLETE)
    fields.setdefault("title", f"Exercise {n}")
    fields.setdefault("slug", f"exercise-{n}")
    fields.setdefault("prompt", f"Prompt for exercise {n}.")
    fields.setdefault("order", lesson.exercises.count() + 1)
    fields.setdefault("content", copy.deepcopy(CONTENT_EXAMPLES.get(response_type, {})))
    fields.setdefault("evaluation_spec", copy.deepcopy(SPEC_EXAMPLES.get(response_type, {})))
    fields.setdefault("is_published", True)
    return Exercise.objects.create(lesson=lesson, **fields)
