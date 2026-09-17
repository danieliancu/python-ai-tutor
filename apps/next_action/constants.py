"""Next Best Action v1: vocabulary, priority tiers and tuning constants.

Decisions are computed on demand and never stored, so the algorithm version is reported with
each decision instead of being persisted.
"""

from apps.curriculum.models import Lesson
from apps.exercises.models import LearningMode

NEXT_ACTION_ALGORITHM_VERSION = 1

# Action types
LEARN = "learn"
PRACTICE = "practice"
REVIEW = "review"
REMEDIATE = "remediate"
COURSE_COMPLETE = "course_complete"
NO_AVAILABLE_ACTION = "no_available_action"

# Reason codes (the structured source of truth; never prose)
ACTIVE_MISCONCEPTION = "active_misconception"
REVIEW_DUE = "review_due"
BELOW_PROGRESSION_THRESHOLD = "below_progression_threshold"
NEW_CONCEPT_READY = "new_concept_ready"
ADVANCED_MODE_GAP = "advanced_mode_gap"
MODE_WEAKNESS = "mode_weakness"
NOT_YET_MASTERED = "not_yet_mastered"
FALLING_TREND = "falling_trend"
WATCH_MISCONCEPTION = "watch_misconception"
WORLD_COMPLETE = "world_complete"
BLOCKED_BY_PREREQUISITES = "blocked_by_prerequisites"
NO_PUBLISHED_EXERCISE = "no_published_exercise"
NO_PUBLISHED_CONTENT = "no_published_content"
REMEDIATION_FALLBACK = "remediation_fallback"

# Priority tiers: only the order matters. Urgency never moves a candidate across tiers.
REMEDIATE_TIER = 500
REVIEW_TIER = 400
STRENGTHEN_TIER = 300
INTRODUCE_TIER = 200
DEEPEN_TIER = 100

# Readiness
PREREQUISITE_MASTERY_THRESHOLD = 65.0
PROGRESSION_THRESHOLD = 65.0
MODE_WEAKNESS_THRESHOLD = 60.0

# Within-tier urgency weights (each component is bounded)
MAX_OVERDUE_DAYS = 30.0
MAX_GAP_COMPONENT = 20.0
GAP_WEIGHT = 0.2
UNKNOWN_RETENTION_COMPONENT = 10.0
STRENGTHEN_GAP_WEIGHT = 0.5
MISSING_MODE_WEIGHT = 5.0
FALLING_TREND_BONUS = 10.0
WATCH_BONUS = 5.0
CONTINUITY_BONUS = 5.0

# Exercise selection
RECENT_EXERCISE_COOLDOWN = 3

MODE_ORDER = (
    LearningMode.RECOGNISE,
    LearningMode.COMPLETE,
    LearningMode.FIX,
    LearningMode.CREATE,
)

LESSON_KIND_PREFERENCES = {
    LEARN: (Lesson.Kind.LEARN, Lesson.Kind.PRACTICE, Lesson.Kind.REVIEW, Lesson.Kind.CHALLENGE),
    PRACTICE: (
        Lesson.Kind.PRACTICE,
        Lesson.Kind.LEARN,
        Lesson.Kind.REVIEW,
        Lesson.Kind.CHALLENGE,
    ),
    REVIEW: (Lesson.Kind.REVIEW, Lesson.Kind.PRACTICE, Lesson.Kind.CHALLENGE, Lesson.Kind.LEARN),
    REMEDIATE: (
        Lesson.Kind.PRACTICE,
        Lesson.Kind.REVIEW,
        Lesson.Kind.LEARN,
        Lesson.Kind.CHALLENGE,
    ),
}
