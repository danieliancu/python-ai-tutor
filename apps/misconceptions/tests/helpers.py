from datetime import timedelta
from types import SimpleNamespace

from apps.attempts.models import AttemptStatus
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.tests.helpers import BASE_TIME, IntelligenceFixtures
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.services import refresh_concept_misconceptions

CORRECT = AttemptStatus.CORRECT
INCORRECT = AttemptStatus.INCORRECT

COMPARISON_REFERENCE = (
    "numbers = [4, 18, 7]\nfor number in numbers:\n    if number > 10:\n        print(number)\n"
)
COMPARISON_TAGS = ["comparison-direction", "comparison-boundary"]


def python_code(reference: str, tags: list[str], **spec) -> dict:
    return {
        "response_type": ResponseType.CODE,
        "content": {"language": "python", "starter_code": ""},
        "evaluation_spec": {
            "strategy": "stdout",
            "tests": [{"stdin": "", "expected_stdout": "SECRET-OUTPUT\n"}],
            "reference_solution": reference,
            "misconceptions": tags,
            **spec,
        },
    }


def fill_gap(template: str, answers: list[str], tags: list[str]) -> dict:
    return {
        "response_type": ResponseType.FILL_GAP,
        "content": {"template": template},
        "evaluation_spec": {
            "accepted_answers": answers,
            "case_sensitive": True,
            "misconceptions": tags,
        },
    }


def choice(tags: list[str]) -> dict:
    return {
        "response_type": ResponseType.MULTIPLE_CHOICE,
        "content": {"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
        "evaluation_spec": {"correct_option": "a", "misconceptions": tags},
    }


def fake_exercise(definition: dict, mode: str = LearningMode.FIX, pk: int = 7) -> Exercise:
    """An unsaved exercise for pure detector tests."""
    return Exercise(pk=pk, learning_mode=mode, target_seconds=None, **definition)


def fake_attempt(
    exercise: Exercise,
    status: str = INCORRECT,
    answer: object = None,
    diagnostics: dict | None = None,
    **fields,
) -> SimpleNamespace:
    judged = status in (CORRECT, INCORRECT)
    values = {
        "pk": 1,
        "exercise": exercise,
        "exercise_id": exercise.pk,
        "status": status,
        "submitted_answer": answer,
        "diagnostics": diagnostics or {},
        "score": (1.0 if status == CORRECT else 0.0) if judged else None,
        "is_correct": (status == CORRECT) if judged else None,
        "hint_level": 0,
        "used_explanation": False,
        "used_solution": False,
        "duration_seconds": None,
        "submitted_at": BASE_TIME,
    }
    values.update(fields)
    return SimpleNamespace(**values)


class MisconceptionFixtures(IntelligenceFixtures):
    """Tagged exercises in the Python, English and Maths concepts of AttemptFixtures."""

    def setUp(self) -> None:
        super().setUp()
        lesson = self.mcq.lesson
        self.tagged = make_exercise(
            lesson, learning_mode=LearningMode.RECOGNISE, **choice(["off-by-one"])
        )
        self.tagged_again = make_exercise(
            lesson, learning_mode=LearningMode.RECOGNISE, **choice(["off-by-one"])
        )
        self.ambiguous = make_exercise(lesson, **choice(["alpha-idea", "beta-idea", "gamma-idea"]))
        self.range_gap = make_exercise(
            lesson,
            learning_mode=LearningMode.COMPLETE,
            **fill_gap(
                "for n in range(1, __):\n    print(n)",
                ["6"],
                ["range-exclusive-stop", "off-by-one"],
            ),
        )
        self.comparison = make_exercise(
            lesson,
            learning_mode=LearningMode.FIX,
            **python_code(COMPARISON_REFERENCE, COMPARISON_TAGS),
        )
        self.article = make_exercise(
            self.translation.lesson,
            learning_mode=LearningMode.COMPLETE,
            **choice(["article-omission"]),
        )
        self.sign = make_exercise(
            self.numeric.lesson,
            response_type=ResponseType.NUMERIC,
            learning_mode=LearningMode.CREATE,
            content={"unit": ""},
            evaluation_spec={"expected": 5, "tolerance": 0, "misconceptions": ["sign-error"]},
        )

    def at(self, minutes: float):
        return BASE_TIME + timedelta(minutes=minutes)

    def wrong(self, exercise, minutes: float = 0, **fields):
        return self.make_attempt(exercise, INCORRECT, at=self.at(minutes), **fields)

    def right(self, exercise, minutes: float = 0, **fields):
        return self.make_attempt(exercise, CORRECT, at=self.at(minutes), **fields)

    def refresh(self, enrollment=None, concept=None):
        return refresh_concept_misconceptions(
            enrollment or self.enrollment, concept or self.concept
        )

    def state(self, code: str, enrollment=None, concept=None) -> MisconceptionState:
        return MisconceptionState.objects.get(
            enrollment=enrollment or self.enrollment, concept=concept or self.concept, code=code
        )

    def evidence(self, **filters):
        return MisconceptionEvidence.objects.filter(**filters)
