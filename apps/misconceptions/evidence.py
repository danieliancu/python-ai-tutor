"""Evidence signals, the detector contract and the generic exercise-tag detector.

Detectors are pure: they read an attempt (and its exercise) and return signals. They never
write rows, never execute learner code and never copy answers into what they return.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from apps.attempts.models import AttemptStatus
from apps.learner_intelligence.scoring import Evidence, assistance_factor
from apps.misconceptions import scoring
from apps.misconceptions.definitions import is_safe_code

POSITIVE = "positive"
COUNTER = "counter"
KINDS = (POSITIVE, COUNTER)

SAFE_DETAIL_KEYS = frozenset({"reason", "error_type", "pattern"})
SAFE_DETAIL_VALUE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def is_safe_details(details: object) -> bool:
    return isinstance(details, Mapping) and all(
        key in SAFE_DETAIL_KEYS
        and isinstance(value, str)
        and SAFE_DETAIL_VALUE.fullmatch(value) is not None
        for key, value in details.items()
    )


@dataclass(frozen=True)
class EvidenceSignal:
    code: str
    kind: str
    strength: float
    source: str
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_safe_code(self.code) or not is_safe_code(self.source):
            raise ValueError("Evidence codes and sources must be safe slugs.")
        if self.kind not in KINDS:
            raise ValueError(f"Unknown evidence kind: {self.kind!r}")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("Evidence strength must be between 0 and 1.")
        if not is_safe_details(self.details):
            raise ValueError("Evidence details may only hold safe codes.")


class Detector(Protocol):
    name: str

    def detect(self, attempt) -> list[EvidenceSignal]: ...


def exercise_tags(exercise) -> list[str]:
    """Candidate misconception codes authored on the exercise (private metadata)."""
    spec = exercise.evaluation_spec if isinstance(exercise.evaluation_spec, dict) else {}
    tags = spec.get("misconceptions") or []
    if not isinstance(tags, list):
        return []
    return list(dict.fromkeys(tag for tag in tags if is_safe_code(tag)))


def counter_evidence_strength(attempt) -> float:
    """Correct work counts against a misconception, less so the more help was used."""
    return assistance_factor(Evidence.from_attempt(attempt))


class GenericTagDetector:
    """Weak candidate evidence from exercise tags: a failure *may* involve any of them."""

    name = "exercise_tag"

    def detect(self, attempt) -> list[EvidenceSignal]:
        tags = exercise_tags(attempt.exercise)
        if attempt.status == AttemptStatus.INCORRECT:
            return [
                EvidenceSignal(tag, POSITIVE, scoring.CANDIDATE_STRENGTH, self.name) for tag in tags
            ]
        if attempt.status == AttemptStatus.CORRECT:
            strength = round(counter_evidence_strength(attempt), 2)
            return [EvidenceSignal(tag, COUNTER, strength, self.name) for tag in tags]
        # invalid, review_required, unsupported and unavailable say nothing about understanding.
        return []
