from apps.evaluation.exceptions import EvaluationError


class RunnerUnavailableError(EvaluationError):
    """The execution infrastructure failed. Never the learner's fault; never shown to them."""


class SourceRejected(ValueError):
    """The submitted source can't be run at all (wrong type, empty, too large, NUL bytes)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
