PUBLIC_UNAVAILABLE_MESSAGE = "This exercise can't be checked right now."


class EvaluationError(Exception):
    """Base class for evaluation failures that are not about the learner's answer."""


class EvaluationConfigurationError(EvaluationError):
    """The exercise itself is misconfigured (a content problem, not a wrong answer).

    ``problem`` is for logs and authors only; show learners ``public_message``.
    """

    public_message = PUBLIC_UNAVAILABLE_MESSAGE

    def __init__(self, exercise_id: int | None, problem: str) -> None:
        self.exercise_id = exercise_id
        self.problem = problem
        super().__init__(f"Exercise {exercise_id} is misconfigured: {problem}")


class EvaluationUnavailable(EvaluationError):
    """Raised to learner-facing callers. Carries only a safe message."""

    def __init__(self, message: str = PUBLIC_UNAVAILABLE_MESSAGE) -> None:
        self.public_message = message
        super().__init__(message)
