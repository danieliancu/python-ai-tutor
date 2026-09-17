"""Immutable, ORM-free tutor data. Providers only ever see these."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssistanceState:
    """AI help given on one exercise since the learner's latest attempt."""

    hint_level: int = 0
    used_explanation: bool = False
    used_solution: bool = False

    def as_dict(self) -> dict:
        return {
            "hint_level": self.hint_level,
            "used_explanation": self.used_explanation,
            "used_solution": self.used_solution,
        }


@dataclass(frozen=True)
class LearnerSubmission:
    """The learner's own latest answer: untrusted data, possibly truncated."""

    text: str
    truncated: bool = False


@dataclass(frozen=True)
class HistoryItem:
    intent: str
    response_kind: str
    user_message: str
    assistant_message: str


@dataclass(frozen=True)
class TutorProviderRequest:
    instructions: str
    server_context: Mapping
    history: tuple[HistoryItem, ...]
    user_message: str
    response_kind: str
    solution_allowed: bool
    max_output_tokens: int
    learner_submission: LearnerSubmission | None = None


@dataclass(frozen=True)
class TutorProviderResult:
    reply: str
    response_kind: str
    should_retry: bool
    provider: str
    model: str
    provider_response_id: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class TutorContext:
    """Everything the provider may see, split by trust level."""

    server: dict
    history: tuple[HistoryItem, ...] = ()
    learner_submission: LearnerSubmission | None = None
    extra: dict = field(default_factory=dict)
