"""Which published exercise best serves a chosen action. Deterministic, never random."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from apps.exercises.models import Exercise
from apps.misconceptions.evidence import exercise_tags
from apps.next_action import constants as c
from apps.next_action.types import ConceptContext

MODE_RANK = {mode: index for index, mode in enumerate(c.MODE_ORDER)}


@dataclass(frozen=True)
class ExercisePick:
    exercise: Exercise
    target_mode: str
    remediation_fallback: bool = False


def choose_target_mode(
    available_modes: Iterable[str],
    successful_modes: Iterable[str],
    performance: Mapping[str, float],
    independence: Mapping[str, float],
    action: str,
) -> str | None:
    """The generic learning mode to aim for, among modes that actually have exercises.

    Earliest mode (recognise → complete → fix → create) without successful evidence first;
    otherwise the weakest mode (reviews also weigh lower independence).
    """
    available = sorted(set(available_modes), key=lambda mode: MODE_RANK.get(mode, len(MODE_RANK)))
    if not available:
        return None
    succeeded = set(successful_modes)
    for mode in available:
        if mode not in succeeded:
            return mode

    def weakness(mode: str) -> tuple:
        key = [performance.get(mode, 0.0)]
        if action == c.REVIEW:
            key.append(independence.get(mode, 0.0))
        return (*key, MODE_RANK.get(mode, len(MODE_RANK)))

    return min(available, key=weakness)


def exercise_sort_key(
    exercise: Exercise,
    *,
    action: str,
    target_mode: str | None,
    attempt_counts: Mapping[int, int],
    recent_ids: Iterable[int],
    active_codes: Sequence[str] = (),
) -> tuple:
    kinds = c.LESSON_KIND_PREFERENCES.get(action, ())
    kind = exercise.lesson.kind
    attempts = attempt_counts.get(exercise.pk, 0)
    key = []
    if action == c.REMEDIATE:
        tags = set(exercise_tags(exercise))
        primary = active_codes[0] if active_codes else None
        key += [primary not in tags, -len(tags & set(active_codes))]
    key += [
        exercise.learning_mode != target_mode,
        kinds.index(kind) if kind in kinds else len(kinds),
        exercise.pk in set(recent_ids),
        attempts > 0,
        attempts,
        exercise.lesson.order,
        exercise.order,
        exercise.pk,
    ]
    return tuple(key)


def pick_exercise(
    exercises: Sequence[Exercise],
    *,
    action: str,
    context: ConceptContext,
    attempt_counts: Mapping[int, int],
    recent_ids: Iterable[int] = (),
    active_codes: Sequence[str] = (),
) -> ExercisePick | None:
    """The best exercise among the concept's published ``exercises``; None only if empty.

    Recently seen exercises are ranked lower, never excluded, so there is no dead end.
    """
    if not exercises:
        return None
    pool = list(exercises)
    fallback = False
    if action == c.REMEDIATE:
        codes = set(active_codes)
        tagged = [e for e in pool if codes & set(exercise_tags(e))]
        if tagged:
            pool = tagged
        else:
            fallback = True
    target_mode = choose_target_mode(
        {e.learning_mode for e in pool},
        context.mode_success,
        context.mode_performance,
        context.mode_independence,
        action,
    )
    recent = set(recent_ids)
    best = min(
        pool,
        key=lambda exercise: exercise_sort_key(
            exercise,
            action=action,
            target_mode=target_mode,
            attempt_counts=attempt_counts,
            recent_ids=recent,
            active_codes=active_codes,
        ),
    )
    return ExercisePick(best, target_mode=best.learning_mode, remediation_fallback=fallback)
