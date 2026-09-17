"""Learner-facing wording and safe feedback for the course player.

Only display text lives here. Decisions (correctness, mastery, next exercise, help level) come
from the existing services.
"""

from apps.attempts.mistakes import safe_diagnostics
from apps.exercises.models import ResponseType

BOSS_LABEL = "Boss Challenge"

KICKERS = {
    ResponseType.CODE: "Coding Exercise",
    ResponseType.MULTIPLE_CHOICE: "Multiple Choice",
    ResponseType.FILL_GAP: "Fill the Gap",
    ResponseType.NUMERIC: "Numeric Answer",
    ResponseType.TEXT: "Written Answer",
    ResponseType.TRANSLATION: "Translation",
    ResponseType.MATH_EXPRESSION: "Maths Expression",
}
EDITOR_TABS = {
    ResponseType.CODE: "main.py",
    ResponseType.MULTIPLE_CHOICE: "Choose one",
    ResponseType.FILL_GAP: "Fill the gap",
    ResponseType.NUMERIC: "Your answer",
    ResponseType.TEXT: "Your answer",
    ResponseType.TRANSLATION: "Your translation",
    ResponseType.MATH_EXPRESSION: "Your answer",
}
# Types that are answered with free text in a textarea.
TEXT_TYPES = frozenset({ResponseType.TEXT, ResponseType.TRANSLATION})
LINE_TYPES = frozenset({ResponseType.NUMERIC, ResponseType.MATH_EXPRESSION})
SUPPORTED_TYPES = frozenset(
    {ResponseType.CODE, ResponseType.MULTIPLE_CHOICE, ResponseType.FILL_GAP}
    | TEXT_TYPES
    | LINE_TYPES
)

ACTION_LABELS = {
    "learn": "Learn",
    "practice": "Practice",
    "review": "Review",
    "remediate": "Fix a misconception",
    "course_complete": "Complete",
    "no_available_action": "Up next",
}
ACTION_BUTTONS = {
    "learn": "Continue",
    "practice": "Keep practising",
    "review": "Review now",
    "remediate": "Try this exercise",
}
REASON_TEXT = {
    "new_concept_ready": "You're ready for something new.",
    "below_progression_threshold": "A little more practice will make this stick.",
    "review_due": "Time for a quick review so it stays fresh.",
    "active_misconception": "Let's clear up an idea that keeps tripping you up.",
    "not_yet_mastered": "Keep building on what you've learned.",
    "advanced_mode_gap": "Try this idea in a new way.",
    "mode_weakness": "Strengthen one way of using this idea.",
    "falling_trend": "Let's reinforce this before moving on.",
    "watch_misconception": "A quick check on a common mix-up.",
    "world_complete": "You've mastered every concept in this course. Well done!",
    "blocked_by_prerequisites": "There's no available next exercise right now.",
    "no_published_exercise": "There's no available next exercise right now.",
    "no_published_content": "This course has no exercises yet.",
}
STATUS_LABELS = {
    "correct": "✓ Correct.",
    "incorrect": "✗ Not quite yet.",
    "invalid": "! Check your answer format.",
    "review_required": "… Saved. This answer needs a review; it isn't marked right or wrong.",
    "unsupported": "! This answer can't be checked automatically yet.",
    "unavailable": "! We couldn't check your answer right now. Please try again.",
}
IDLE_OUTPUT = {
    ResponseType.CODE: "Run your code to check it.",
}
DEFAULT_IDLE_OUTPUT = "Check your answer to see feedback here."
TUTOR_UNAVAILABLE = "AI Tutor is currently unavailable."
TUTOR_INTRO = (
    "Ask me anything about this exercise. Type /hint for a hint, /explain for an "
    "explanation, /solution to work towards the answer, or /next for what to do next."
)


def feedback_lines(attempt: dict) -> list[str]:
    """Safe feedback for an attempt payload (``attempt_list_item`` shape)."""
    lines = [STATUS_LABELS.get(attempt.get("status"), "Answer recorded.")]
    message = attempt.get("message")
    if message and attempt.get("status") != "correct":
        lines.append(message)
    diagnostics = safe_diagnostics(attempt.get("diagnostics") or {})
    if diagnostics.get("error_type"):
        lines.append(f"Error: {diagnostics['error_type']}")
    elif diagnostics.get("reason") and attempt.get("status") not in ("correct",):
        lines.append(f"Reason: {diagnostics['reason'].replace('_', ' ')}")
    return lines


def next_up_view(decision: dict, player_url: str, boss_ids=()) -> dict:
    """Card text for a public next-action payload (``decision_presentation`` shape)."""
    action = decision["action"]
    exercise = decision.get("exercise")
    concept = decision.get("concept")
    if action == "course_complete":
        title = "Course complete"
    elif concept:
        title = concept["title"]
    else:
        title = "Nothing to do right now"
    return {
        # A boss is still the pedagogical choice; it is only labelled as a checkpoint.
        "badge": (
            BOSS_LABEL
            if exercise and exercise["id"] in boss_ids
            else ACTION_LABELS.get(action, "Up next")
        ),
        "title": title,
        "description": REASON_TEXT.get(decision["primary_reason"], ""),
        "button": ACTION_BUTTONS.get(action, "Continue"),
        "href": f"{player_url}?exercise={exercise['id']}" if exercise else "",
        "action": action,
    }
