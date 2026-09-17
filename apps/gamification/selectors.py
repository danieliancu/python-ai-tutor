"""Read-only gamification data for pages. Nothing here writes or scans history."""

from datetime import date

from django.db.models import Sum
from django.utils import timezone

from apps.attempts.models import ExerciseAttempt
from apps.gamification.levels import level_progress
from apps.gamification.models import (
    Achievement,
    AchievementAward,
    GamificationProfile,
    XPEvent,
)
from apps.gamification.streaks import effective_streak
from apps.learners.models import LearnerProfile


def header_stats(learner: LearnerProfile, today: date | None = None) -> dict:
    """XP, level and streak for the header (one query; a learner without a profile has 0)."""
    profile = GamificationProfile.objects.filter(learner=learner).first()
    total = profile.total_xp if profile else 0
    progress = level_progress(total)
    streak = (
        effective_streak(
            profile.current_streak,
            profile.last_activity_date,
            today or timezone.localdate(),
        )
        if profile
        else 0
    )
    return {
        "xp": total,
        "xp_display": f"{total:,}",
        "level": progress["level"],
        "level_percent": progress["percent"],
        "next_level_xp": progress["next"],
        "streak_days": streak,
        "longest_streak": profile.longest_streak if profile else 0,
    }


def attempt_rewards(attempt: ExerciseAttempt) -> dict:
    """What this attempt earned: XP and newly unlocked achievements."""
    xp = XPEvent.objects.filter(attempt=attempt).aggregate(total=Sum("xp"))["total"] or 0
    awards = AchievementAward.objects.filter(attempt=attempt).select_related("achievement")
    return {
        "xp": xp,
        "achievements": [
            {"title": award.achievement.title, "description": award.achievement.description}
            for award in awards
        ],
    }


def submission_rewards(submission) -> dict:
    """What a project submission earned: XP and newly unlocked achievements."""
    xp = (
        XPEvent.objects.filter(project_submission=submission).aggregate(total=Sum("xp"))["total"]
        or 0
    )
    awards = AchievementAward.objects.filter(project_submission=submission).select_related(
        "achievement"
    )
    return {
        "xp": xp,
        "achievements": [
            {"title": award.achievement.title, "description": award.achievement.description}
            for award in awards
        ],
    }


def profile_summary(learner: LearnerProfile) -> dict:
    awards = list(
        AchievementAward.objects.filter(learner=learner)
        .select_related("achievement")
        .order_by("awarded_at", "id")
    )
    return {
        **header_stats(learner),
        "awards": awards,
        "achievement_total": Achievement.objects.filter(is_active=True).count(),
    }
