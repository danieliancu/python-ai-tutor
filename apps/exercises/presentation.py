"""The learner-facing view of an Exercise.

This is an explicit allow-list. Adding a model field never exposes it by accident, and
``evaluation_spec`` is never part of it.
"""

import copy

from apps.exercises.models import Exercise

PUBLIC_FIELDS = (
    "id",
    "title",
    "slug",
    "prompt",
    "instructions",
    "response_type",
    "learning_mode",
    "content",
    "target_seconds",
)


def exercise_presentation(exercise: Exercise) -> dict:
    return {
        "id": exercise.pk,
        "title": exercise.title,
        "slug": exercise.slug,
        "prompt": exercise.prompt,
        "instructions": exercise.instructions,
        "response_type": exercise.response_type,
        "learning_mode": exercise.learning_mode,
        # A copy, so callers can't mutate the model's data through the payload.
        "content": copy.deepcopy(exercise.content),
        "target_seconds": exercise.target_seconds,
    }
