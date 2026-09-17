"""AI tutor vocabulary and limits."""

from django.db import models

# Bump whenever the teaching policy or prompt structure changes.
TUTOR_PROMPT_VERSION = 1

MAX_HINT_LEVEL = 2
MAX_SUBMISSION_BYTES = 8 * 1024
HISTORY_DEFAULT = 20
HISTORY_MAX = 50
RATE_WINDOW_SECONDS = 60


class Intent(models.TextChoices):
    """What the learner asked for. A request, never an authorisation."""

    ASK = "ask", "Ask"
    HINT = "hint", "Hint"
    EXPLAIN = "explain", "Explain"
    SOLUTION = "solution", "Solution"
    NEXT_STEP = "next_step", "Next step"


class ResponseKind(models.TextChoices):
    """The pedagogical level the server granted for one reply."""

    GUIDANCE = "guidance", "Guidance"
    HINT = "hint", "Hint"
    STRONG_HINT = "strong_hint", "Strong hint"
    EXPLANATION = "explanation", "Explanation"
    SOLUTION = "solution", "Solution"
    FEEDBACK = "feedback", "Feedback"
    NEXT_STEP = "next_step", "Next step"


class TurnStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"


# Intents that are about one exercise and change its assistance record.
EXERCISE_HELP_INTENTS = frozenset({Intent.HINT, Intent.EXPLAIN, Intent.SOLUTION})

# Safe, stored error codes.
PROVIDER_TIMEOUT = "provider_timeout"
PROVIDER_UNAVAILABLE = "provider_unavailable"
PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
PROVIDER_RATE_LIMITED = "provider_rate_limited"

# Public API error codes.
TUTOR_UNAVAILABLE = "tutor_unavailable"
TUTOR_RATE_LIMITED = "tutor_rate_limited"
RATE_LIMITED = "rate_limited"
INVALID_INTENT = "invalid_intent"
MESSAGE_REQUIRED = "message_required"
MESSAGE_TOO_LONG = "message_too_long"
INVALID_MESSAGE = "invalid_message"
NO_EXERCISE_CONTEXT = "no_exercise_context"
FORBIDDEN = "forbidden"
