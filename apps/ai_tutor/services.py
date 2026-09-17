"""Tutor turn orchestration.

Django decides everything about the turn (exercise, allowed help level, learner facts); the
provider only writes the reply. Provider calls happen outside database transactions, and a
failed call never changes assistance or learner state.
"""

import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ai_tutor import assistance
from apps.ai_tutor.adapters import adapter_for
from apps.ai_tutor.config import get_tutor_config
from apps.ai_tutor.constants import (
    EXERCISE_HELP_INTENTS,
    FORBIDDEN,
    INTERNAL_ERROR,
    INVALID_INTENT,
    INVALID_MESSAGE,
    MESSAGE_REQUIRED,
    MESSAGE_TOO_LONG,
    NO_EXERCISE_CONTEXT,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMITED,
    RATE_LIMITED,
    RATE_WINDOW_SECONDS,
    TUTOR_PROMPT_VERSION,
    TUTOR_RATE_LIMITED,
    TUTOR_TURN_IN_PROGRESS,
    TUTOR_UNAVAILABLE,
    Intent,
    TurnStatus,
)
from apps.ai_tutor.context import build_tutor_context
from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.pedagogy import disclosure_for, grant_response_kind, solution_allowed
from apps.ai_tutor.prompts import build_instructions, button_message
from apps.ai_tutor.providers import get_provider
from apps.ai_tutor.providers.base import TutorError, TutorInvalidResponse
from apps.ai_tutor.types import AssistanceState, TutorProviderRequest
from apps.attempts.models import ExerciseAttempt
from apps.exercises.models import Exercise
from apps.exercises.selectors import published_exercises
from apps.learners.models import Enrollment
from apps.next_action.engine import next_action_for_enrollment

logger = logging.getLogger(__name__)


class TutorRequestError(Exception):
    """A request the tutor can't serve, with a safe public code and HTTP status."""

    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class TutorTurnOutcome:
    turn: TutorTurn
    assistance: AssistanceState


def _validate(intent: object, message: object, max_chars: int) -> tuple[Intent, str]:
    if intent not in Intent.values:
        raise TutorRequestError(INVALID_INTENT, 400)
    if message is None:
        message = ""
    if not isinstance(message, str):
        raise TutorRequestError(INVALID_MESSAGE, 400)
    if len(message) > max_chars:
        raise TutorRequestError(MESSAGE_TOO_LONG, 400)
    if intent == Intent.ASK and not message.strip():
        raise TutorRequestError(MESSAGE_REQUIRED, 400)
    return Intent(intent), message.strip()


def rate_limited(enrollment: Enrollment, limit: int, now) -> bool:
    since = now - timedelta(seconds=RATE_WINDOW_SECONDS)
    return TutorTurn.objects.filter(enrollment=enrollment, created_at__gt=since).count() >= limit


def resolve_exercise(enrollment: Enrollment, exercise_id: int) -> Exercise:
    """A published exercise in the enrollment's own World, or a 403."""
    exercise = (
        published_exercises()
        .filter(pk=exercise_id, lesson__concept__skill__world_id=enrollment.world_id)
        .select_related("lesson__concept__skill")
        .first()
    )
    if exercise is None:
        raise TutorRequestError(FORBIDDEN, 403)
    return exercise


def latest_attempt(enrollment: Enrollment, exercise: Exercise | None) -> ExerciseAttempt | None:
    if exercise is None:
        return None
    return (
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise)
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")
        .first()
    )


def request_tutor_turn(
    enrollment: Enrollment,
    *,
    intent: object = Intent.ASK,
    message: object = "",
    exercise_id: int | None = None,
    now=None,
    provider=None,
) -> TutorTurnOutcome:
    config = get_tutor_config()
    intent, message = _validate(intent, message, config.max_user_chars)
    if not config.available:
        raise TutorRequestError(TUTOR_UNAVAILABLE, 503)
    now = now or timezone.now()
    if rate_limited(enrollment, config.rate_limit_per_minute, now):
        raise TutorRequestError(RATE_LIMITED, 429)

    decision = next_action_for_enrollment(enrollment, now=now)
    exercise = None
    if exercise_id is not None and intent != Intent.NEXT_STEP:
        exercise = resolve_exercise(enrollment, exercise_id)
    elif intent in EXERCISE_HELP_INTENTS:
        if decision.exercise_id is None:
            raise TutorRequestError(NO_EXERCISE_CONTEXT, 400)
        exercise = resolve_exercise(enrollment, decision.exercise_id)

    provider = provider or get_provider(config)
    reservation = _reserve_turn(enrollment, exercise, intent, message, provider, config.model, now)
    turn, attempt, state, granted = reservation

    adapter = adapter_for(enrollment.world)
    try:
        request, private_context = _build_request(
            enrollment,
            exercise=exercise,
            attempt=attempt,
            state=state,
            granted=granted,
            intent=intent,
            message=message,
            decision=decision,
            adapter=adapter,
            config=config,
            now=now,
        )
    except Exception:
        # Never leave a reservation behind.
        _fail(turn, INTERNAL_ERROR, None)
        raise

    started = time.monotonic()
    try:
        result = provider.generate(request)
        if result.response_kind != granted:
            # The model may never pick its own level.
            raise TutorInvalidResponse()
        reply = adapter.postprocess_reply(result.reply)
        adapter.validate_reply(
            reply, granted=granted, exercise=exercise, private_context=private_context
        )
    except TutorError as exc:
        _fail(turn, exc.code, _elapsed(started))
        if exc.code == PROVIDER_RATE_LIMITED:
            raise TutorRequestError(TUTOR_RATE_LIMITED, 429) from None
        raise TutorRequestError(TUTOR_UNAVAILABLE, 503) from None
    except Exception:
        _fail(turn, INTERNAL_ERROR, _elapsed(started))
        raise
    latency = _elapsed(started)

    try:
        with transaction.atomic():
            # Same lock as attempt storage: a reply and an attempt never interleave.
            Enrollment.objects.select_for_update().filter(pk=enrollment.pk).first()
            turn.status = TurnStatus.COMPLETE
            turn.completed_at = timezone.now()
            turn.response_kind = granted
            turn.assistant_message = reply
            turn.should_retry = result.should_retry
            turn.provider = result.provider
            turn.model = result.model[:100]
            turn.provider_response_id = result.provider_response_id
            turn.input_tokens = result.input_tokens
            turn.output_tokens = result.output_tokens
            turn.latency_ms = latency
            turn.save()
            if exercise is not None:
                # Completed turns record delivered help; the cached state follows them.
                state = assistance.reconcile_assistance_state(enrollment, exercise)
    except Exception:
        _fail(turn, INTERNAL_ERROR, latency)
        raise
    return TutorTurnOutcome(turn=turn, assistance=state)


def _reserve_turn(enrollment, exercise, intent, message, provider, model, now):
    """Create the PENDING turn, then decide the help level from committed history.

    Exercise-scoped turns are limited to one pending turn per learner and exercise by the
    database. The reservation is created *before* assistance is read, so a request that wins
    it always sees help already delivered by earlier turns.
    """
    if exercise is not None:
        assistance.expire_stale_turns(enrollment, exercise, now)
    try:
        with transaction.atomic():
            turn = TutorTurn.objects.create(
                enrollment=enrollment,
                exercise=exercise,
                requested_intent=intent,
                user_message=message,
                status=TurnStatus.PENDING,
                provider=provider.name,
                prompt_version=TUTOR_PROMPT_VERSION,
                model=model,
                created_at=now,
            )
            attempt = latest_attempt(enrollment, exercise)
            state = (
                assistance.reconcile_assistance_state(enrollment, exercise)
                if exercise is not None
                else AssistanceState()
            )
            granted = grant_response_kind(intent, state, has_attempt=attempt is not None)
            turn.attempt = attempt
            turn.response_kind = granted
            turn.save(update_fields=["attempt", "response_kind"])
    except IntegrityError:
        raise TutorRequestError(TUTOR_TURN_IN_PROGRESS, 409) from None
    return turn, attempt, state, granted


def _build_request(
    enrollment,
    *,
    exercise,
    attempt,
    state,
    granted,
    intent,
    message,
    decision,
    adapter,
    config,
    now,
):
    context = build_tutor_context(
        enrollment,
        exercise=exercise,
        latest_attempt=attempt,
        assistance=state,
        granted=granted,
        decision=decision,
        history_turns=config.history_turns,
        now=now,
    )
    private_context = adapter.private_teaching_context(
        enrollment=enrollment,
        exercise=exercise,
        latest_attempt=attempt,
        granted=granted,
        assistance=state,
        server_context=context.server,
    )
    if private_context:
        context.server["private_teaching"] = private_context
    allowed = solution_allowed(state, granted)
    request = TutorProviderRequest(
        instructions=build_instructions(
            granted=granted,
            disclosure=disclosure_for(state, granted),
            solution_allowed=allowed,
            adapter_instructions=adapter.extra_instructions(
                server_context=context.server, granted=granted, exercise=exercise
            ),
        ),
        server_context=context.server,
        history=context.history,
        learner_submission=context.learner_submission,
        user_message=message or button_message(intent),
        response_kind=granted,
        solution_allowed=allowed,
        max_output_tokens=config.max_output_tokens,
    )
    return request, private_context


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _fail(turn: TutorTurn, code: str, latency: int | None) -> None:
    """Record a failed turn and release its reservation. Never raises."""
    try:
        TutorTurn.objects.filter(pk=turn.pk, status=TurnStatus.PENDING).update(
            status=TurnStatus.FAILED,
            error_code=code or PROVIDER_INVALID_RESPONSE,
            completed_at=timezone.now(),
            latency_ms=latency,
        )
        turn.refresh_from_db()
    except Exception:
        logger.exception("Could not mark tutor turn %s as failed.", turn.pk)
        return
    logger.warning("Tutor turn %s failed: %s", turn.pk, turn.error_code)


# Shared building blocks for other tutor surfaces (the project coach).
validate_turn_input = _validate
fail_turn = _fail
elapsed_ms = _elapsed
