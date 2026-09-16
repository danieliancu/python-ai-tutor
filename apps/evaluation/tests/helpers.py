from apps.exercises.models import Exercise, LearningMode, ResponseType


def exercise(response_type: str, content=None, spec=None, pk: int = 7) -> Exercise:
    """An unsaved Exercise. Evaluators only read the instance, so no database is needed,
    and deliberately broken configurations can be built without model validation."""
    return Exercise(
        pk=pk,
        title="Exercise",
        slug="exercise",
        prompt="Prompt",
        order=1,
        response_type=response_type,
        learning_mode=LearningMode.RECOGNISE,
        content={} if content is None else content,
        evaluation_spec={} if spec is None else spec,
        is_published=True,
    )


def mcq(correct: object = "opt-b", options=("opt-a", "opt-b", "opt-c")) -> Exercise:
    return exercise(
        ResponseType.MULTIPLE_CHOICE,
        {"options": [{"id": option_id, "text": f"Option {option_id}"} for option_id in options]},
        {"correct_option": correct, "explanation": "Because."},
    )


def fill_gap(answers=(">=",), **spec) -> Exercise:
    return exercise(
        ResponseType.FILL_GAP,
        {"template": "if value __ 10:"},
        {"accepted_answers": list(answers), **spec},
    )


def numeric(expected: object = 12.5, **spec) -> Exercise:
    return exercise(ResponseType.NUMERIC, {"unit": "cm"}, {"expected": expected, **spec})
