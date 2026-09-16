"""The single result type every evaluator returns.

Results are in memory only. ``message`` is safe to show learners; ``diagnostics`` holds
reason codes for future attempt analysis and never contains answers.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class EvaluationStatus(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    INVALID = "invalid"
    REVIEW_REQUIRED = "review_required"
    UNSUPPORTED = "unsupported"


# Statuses where the answer was judged, so a score and is_correct are known.
JUDGED_STATUSES = frozenset({EvaluationStatus.CORRECT, EvaluationStatus.INCORRECT})

MESSAGE_CORRECT = "Correct."
MESSAGE_INCORRECT = "That answer isn't correct yet."
MESSAGE_INVALID = "That answer can't be checked. Please check its format."
MESSAGE_REVIEW = "This answer needs further evaluation."
MESSAGE_UNSUPPORTED = "Automatic checking isn't available for this exercise yet."


@dataclass(frozen=True)
class EvaluationResult:
    status: EvaluationStatus
    evaluator: str
    message: str
    score: float | None = None
    is_correct: bool | None = None
    diagnostics: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", EvaluationStatus(self.status))
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0.")
        if self.status in JUDGED_STATUSES:
            if self.score is None or self.is_correct is None:
                raise ValueError(f"A {self.status} result needs a score and is_correct.")
            if self.is_correct != (self.status == EvaluationStatus.CORRECT):
                raise ValueError("is_correct must match the status.")
        elif self.score is not None or self.is_correct is not None:
            raise ValueError(f"A {self.status} result has no score or is_correct.")


def correct(evaluator: str) -> EvaluationResult:
    return EvaluationResult(
        EvaluationStatus.CORRECT, evaluator, MESSAGE_CORRECT, score=1.0, is_correct=True
    )


def incorrect(evaluator: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        EvaluationStatus.INCORRECT,
        evaluator,
        MESSAGE_INCORRECT,
        score=0.0,
        is_correct=False,
        diagnostics={"reason": reason},
    )


def invalid(evaluator: str, reason: str, message: str = MESSAGE_INVALID) -> EvaluationResult:
    return EvaluationResult(
        EvaluationStatus.INVALID, evaluator, message, diagnostics={"reason": reason}
    )


def review_required(evaluator: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        EvaluationStatus.REVIEW_REQUIRED, evaluator, MESSAGE_REVIEW, diagnostics={"reason": reason}
    )


def unsupported(
    evaluator: str, reason: str, message: str = MESSAGE_UNSUPPORTED
) -> EvaluationResult:
    return EvaluationResult(
        EvaluationStatus.UNSUPPORTED, evaluator, message, diagnostics={"reason": reason}
    )
