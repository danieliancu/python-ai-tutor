"""The one place that decides what the tutor model may see.

``server`` holds authoritative, learner-visible facts only: never evaluation specs, answers,
hidden tests, reference solutions or misconception evidence. The learner's own submission is
kept apart as untrusted data, and history is kept apart as conversation.
"""

import json
from datetime import datetime

from django.utils import timezone

from apps.ai_tutor.constants import MAX_SUBMISSION_BYTES, TurnStatus
from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.pedagogy import disclosure_for, solution_allowed
from apps.ai_tutor.types import AssistanceState, HistoryItem, LearnerSubmission, TutorContext
from apps.attempts.mistakes import safe_diagnostics
from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.exercises.models import Exercise
from apps.exercises.presentation import exercise_presentation
from apps.learner_intelligence.selectors import (
    concept_state_for,
    is_review_due,
    world_summary,
)
from apps.learners.models import Enrollment
from apps.misconceptions.definitions import get_definition, title_for
from apps.misconceptions.models import MisconceptionStatus
from apps.misconceptions.selectors import misconceptions_for_concept, misconceptions_for_world
from apps.next_action.presentation import decision_presentation
from apps.next_action.types import NextActionDecision

JUDGED = (AttemptStatus.CORRECT, AttemptStatus.INCORRECT)
VISIBLE_MISCONCEPTIONS = (MisconceptionStatus.ACTIVE, MisconceptionStatus.WATCH)


def _number(value) -> float | None:
    return None if value is None else float(value)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def truncate_submission(answer: object) -> LearnerSubmission | None:
    """The learner's answer as text, cut to MAX_SUBMISSION_BYTES on a character boundary."""
    if answer is None:
        return None
    text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_SUBMISSION_BYTES:
        return LearnerSubmission(text=text)
    cut = encoded[:MAX_SUBMISSION_BYTES].decode("utf-8", errors="ignore")
    return LearnerSubmission(text=cut, truncated=True)


def _curriculum(exercise: Exercise) -> dict:
    lesson = exercise.lesson
    concept = lesson.concept
    return {
        "skill": {"title": concept.skill.title},
        "concept": {
            "id": concept.pk,
            "title": concept.title,
            "learning_objective": concept.learning_objective,
        },
        "lesson": {
            "title": lesson.title,
            "objective": lesson.objective,
            "summary": lesson.summary,
            "kind": lesson.kind,
        },
    }


def _evaluation(attempt: ExerciseAttempt | None) -> dict:
    if attempt is None:
        return {
            "has_evaluated_attempt": False,
            "authoritative_status": None,
            "note": (
                "No submission has been evaluated for this exercise. Correctness is unknown: "
                "do not say whether any answer is right; ask the learner to submit it."
            ),
            "latest_attempt": None,
        }
    judged = attempt.status in JUDGED
    return {
        "has_evaluated_attempt": judged,
        "authoritative_status": attempt.status,
        "note": (
            "This status comes from the deterministic evaluator and is final."
            if judged
            else "The latest submission could not be judged; correctness is unknown."
        ),
        "latest_attempt": {
            "id": attempt.pk,
            "status": attempt.status,
            "score": attempt.score,
            "is_correct": attempt.is_correct,
            "message": attempt.message,
            "diagnostics": safe_diagnostics(attempt.diagnostics),
            "mistake_codes": [mistake.code for mistake in attempt.mistakes.all()],
            "hint_level": attempt.hint_level,
            "used_explanation": attempt.used_explanation,
            "used_solution": attempt.used_solution,
            "duration_seconds": attempt.duration_seconds,
            "submitted_at": attempt.submitted_at.isoformat(),
        },
    }


def _concept_state(enrollment: Enrollment, concept, now: datetime) -> dict | None:
    state = concept_state_for(enrollment, concept)
    if state is None:
        return None
    return {
        "mastery": float(state.mastery_score),
        "mastery_band": state.mastery_band,
        "retention": _number(state.retention_score),
        "independence": _number(state.independence_score),
        "fluency": _number(state.fluency_score),
        "trend": state.trend,
        "review_due": is_review_due(state, now),
        "modes": {
            mode.learning_mode: {
                "performance": float(mode.performance_score),
                "attempt_count": mode.attempt_count,
                "correct_count": mode.correct_count,
                "independence": _number(mode.independence_score),
                "fluency": _number(mode.fluency_score),
            }
            for mode in state.mode_states.all()
        },
    }


def _misconceptions(enrollment: Enrollment, concept) -> list[dict]:
    items = []
    for state in misconceptions_for_concept(enrollment, concept):
        if state.status not in VISIBLE_MISCONCEPTIONS:
            continue
        definition = get_definition(state.code)
        items.append(
            {
                "code": state.code,
                "title": title_for(state.code),
                "description": definition.description if definition else "",
                "status": state.status,
                "confidence": float(state.confidence_score),
            }
        )
    return items


def _next_action(decision: NextActionDecision, enrollment: Enrollment) -> dict:
    public = decision_presentation(decision, enrollment)
    exercise = public["exercise"]
    return {
        "action": public["action"],
        "primary_reason": public["primary_reason"],
        "reason_codes": public["reason_codes"],
        "skill": public["skill"],
        "concept": public["concept"],
        "lesson": public["lesson"],
        "exercise": {"id": exercise["id"], "title": exercise["title"]} if exercise else None,
        "target_learning_mode": public["target_learning_mode"],
        "misconceptions": public["misconceptions"],
        "note": "Decided by the platform. Explain it; never change or replace it.",
    }


def _world_summary(enrollment: Enrollment, now: datetime) -> dict:
    summary = world_summary(enrollment, now=now)
    statuses = [state.status for state in misconceptions_for_world(enrollment)]
    summary["active_misconceptions"] = statuses.count(MisconceptionStatus.ACTIVE)
    summary["watch_misconceptions"] = statuses.count(MisconceptionStatus.WATCH)
    return summary


def recent_history(enrollment: Enrollment, limit: int) -> tuple[HistoryItem, ...]:
    if limit <= 0:
        return ()
    turns = list(
        TutorTurn.objects.filter(enrollment=enrollment, status=TurnStatus.COMPLETE).order_by(
            "-created_at", "-id"
        )[:limit]
    )
    return tuple(
        HistoryItem(
            intent=turn.requested_intent,
            response_kind=turn.response_kind,
            user_message=turn.user_message,
            assistant_message=turn.assistant_message,
        )
        for turn in reversed(turns)
    )


def build_tutor_context(
    enrollment: Enrollment,
    *,
    exercise: Exercise | None,
    latest_attempt: ExerciseAttempt | None,
    assistance: AssistanceState,
    granted: str,
    decision: NextActionDecision,
    history_turns: int,
    private_teaching: dict | None = None,
    now: datetime | None = None,
) -> TutorContext:
    now = now or timezone.now()
    world = enrollment.world
    server: dict = {
        "world": {"id": world.pk, "title": world.title, "description": world.description},
        "world_summary": _world_summary(enrollment, now),
        "next_action": _next_action(decision, enrollment),
        "assistance": {
            **assistance.as_dict(),
            "granted_response_kind": str(granted),
            "max_disclosure": str(disclosure_for(assistance, granted)),
            "solution_allowed": solution_allowed(assistance, granted),
        },
    }
    submission = None
    if exercise is not None:
        concept = exercise.lesson.concept
        server["curriculum"] = _curriculum(exercise)
        server["exercise"] = exercise_presentation(exercise)
        server["evaluation"] = _evaluation(latest_attempt)
        server["concept_state"] = _concept_state(enrollment, concept, now)
        server["misconceptions"] = _misconceptions(enrollment, concept)
        if latest_attempt is not None:
            submission = truncate_submission(latest_attempt.submitted_answer)
    else:
        server["evaluation"] = {
            "has_evaluated_attempt": False,
            "authoritative_status": None,
            "note": "No exercise is in focus. Do not judge any answer's correctness.",
            "latest_attempt": None,
        }
    if private_teaching:
        server["private_teaching"] = private_teaching
    return TutorContext(
        server=server,
        history=recent_history(enrollment, history_turns),
        learner_submission=submission,
    )
