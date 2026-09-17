"""Reasons an attempt can't be recorded right now (the learner may simply retry)."""


class AttemptTemporarilyBlocked(Exception):
    code = "attempt_blocked"
    status = 503
    message = "Your answer could not be recorded right now. Please try again."


class AttemptTutorTurnInProgress(AttemptTemporarilyBlocked):
    """A tutor reply for this exercise is still being generated.

    Until it finishes we can't know whether its help belongs to this submission.
    """

    code = "tutor_turn_in_progress"
    status = 409
    message = "A tutor response for this exercise is still being generated. Please try again."


class AttemptAssistanceUnavailable(AttemptTemporarilyBlocked):
    """Server-known AI help couldn't be determined, so the attempt isn't stored."""

    code = "assistance_unavailable"
    status = 503
    message = "Your answer could not be recorded safely right now. Please try again."
