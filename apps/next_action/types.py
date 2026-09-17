"""Immutable, ORM-free structures used by the decision logic."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ActiveMisconception:
    code: str
    confidence: float
    last_seen_at: datetime


@dataclass(frozen=True)
class ConceptContext:
    """Everything the policy needs to know about one published concept for one learner."""

    concept_id: int
    skill_id: int
    skill_order: int
    concept_order: int
    started: bool = False
    has_state: bool = False
    mastery: float = 0.0
    band: str = "not_started"
    trend: str = "insufficient_data"
    retention: float | None = None
    review_due_at: datetime | None = None
    active_misconceptions: tuple[ActiveMisconception, ...] = ()
    watch_codes: tuple[str, ...] = ()
    mode_success: frozenset[str] = frozenset()
    mode_performance: dict[str, float] = field(default_factory=dict)
    mode_independence: dict[str, float] = field(default_factory=dict)
    available_modes: frozenset[str] = frozenset()
    prerequisites_ready: bool = False
    is_most_recent: bool = False

    @property
    def has_exercises(self) -> bool:
        return bool(self.available_modes)


@dataclass(frozen=True)
class ActionCandidate:
    action_type: str
    concept_id: int
    priority_tier: int
    urgency_score: float
    reason_codes: tuple[str, ...]
    skill_order: int
    concept_order: int
    misconception_codes: tuple[str, ...] = ()

    @property
    def rank_key(self) -> tuple:
        return (
            -self.priority_tier,
            -round(self.urgency_score, 6),
            self.skill_order,
            self.concept_order,
            self.concept_id,
        )


@dataclass(frozen=True)
class NextActionDecision:
    algorithm_version: int
    action_type: str
    world_id: int
    primary_reason: str
    reason_codes: tuple[str, ...]
    generated_at: datetime
    skill_id: int | None = None
    concept_id: int | None = None
    lesson_id: int | None = None
    exercise_id: int | None = None
    target_learning_mode: str | None = None
    misconception_codes: tuple[str, ...] = ()
    # Internal ranking details; never part of the public presentation.
    priority_tier: int | None = None
    urgency_score: float | None = None
