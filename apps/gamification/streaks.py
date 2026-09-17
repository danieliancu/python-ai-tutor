"""Streaks: consecutive calendar days (in Django's configured time zone) with judged attempts."""

from collections.abc import Iterable
from datetime import date, timedelta

from apps.attempts.models import AttemptStatus

# A learner who studied and got it wrong still studied. Answers that could not be judged
# (malformed input or checking infrastructure) do not count.
QUALIFYING_STATUSES = (
    AttemptStatus.CORRECT,
    AttemptStatus.INCORRECT,
    AttemptStatus.REVIEW_REQUIRED,
)


def streak_from_days(days: Iterable[date]) -> tuple[int, int, date | None]:
    """(run ending at the last active day, longest run, last active day)."""
    ordered = sorted(set(days))
    if not ordered:
        return 0, 0, None
    longest = run = 1
    for previous, day in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
    return run, longest, ordered[-1]


def effective_streak(current_streak: int, last_activity_date: date | None, today: date) -> int:
    """The streak as shown today: it survives until the day after the last activity ends."""
    if last_activity_date is None or today - last_activity_date > timedelta(days=1):
        return 0
    return current_streak
