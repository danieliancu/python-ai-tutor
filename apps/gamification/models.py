"""Platform-wide gamification: XP, streaks, achievements and Boss Challenges.

Gamification observes learning; it never decides it. Correctness comes from evaluation,
mastery from learner intelligence and the next activity from Next Best Action.

``XPEvent`` is the source of truth for XP. ``GamificationProfile`` is a materialised summary
that ``rebuild_gamification`` can always recompute. Levels are derived from XP (see levels.py).
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.attempts.models import ExerciseAttempt
from apps.curriculum.models import World
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment, LearnerProfile


class GamificationProfile(models.Model):
    learner = models.OneToOneField(
        LearnerProfile, on_delete=models.CASCADE, related_name="gamification"
    )
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["learner_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(longest_streak__gte=models.F("current_streak")),
                name="gamification_profile_longest_covers_current",
            ),
        ]

    def __str__(self) -> str:
        return f"Gamification: {self.learner.user.get_username()}"


class XPEventType(models.TextChoices):
    EXERCISE_COMPLETED = "exercise_completed", "Exercise completed"
    FIRST_TRY = "first_try", "First-try bonus"
    INDEPENDENCE = "independence", "Independence bonus"
    SKILL_MASTERED = "skill_mastered", "Skill mastered"
    BOSS_COMPLETED = "boss_completed", "Boss completed"


class XPEvent(models.Model):
    """One XP award. ``source_key`` makes each award happen at most once per learner."""

    Type = XPEventType

    learner = models.ForeignKey(LearnerProfile, on_delete=models.CASCADE, related_name="xp_events")
    world = models.ForeignKey(World, on_delete=models.PROTECT, related_name="xp_events")
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name="xp_events"
    )
    attempt = models.ForeignKey(
        ExerciseAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="xp_events",
    )
    event_type = models.CharField(max_length=32, choices=XPEventType.choices)
    xp = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    source_key = models.CharField(max_length=120)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "XP event"
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "source_key"], name="gamification_xp_event_unique_source"
            ),
            models.CheckConstraint(condition=Q(xp__gt=0), name="gamification_xp_event_positive"),
            models.CheckConstraint(
                condition=Q(event_type__in=XPEventType.values),
                name="gamification_xp_event_type_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["learner", "-created_at"]),
            models.Index(fields=["world", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"+{self.xp} XP ({self.get_event_type_display()})"


class Rarity(models.TextChoices):
    COMMON = "common", "Common"
    UNCOMMON = "uncommon", "Uncommon"
    RARE = "rare", "Rare"
    EPIC = "epic", "Epic"


class Achievement(models.Model):
    code = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    icon_key = models.SlugField(max_length=32, blank=True)
    rarity = models.CharField(max_length=16, choices=Rarity.choices, default=Rarity.COMMON)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rarity__in=Rarity.values), name="gamification_achievement_rarity_valid"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class AchievementAward(models.Model):
    """An achievement a learner has earned. Achievements are not repeatable."""

    learner = models.ForeignKey(
        LearnerProfile, on_delete=models.CASCADE, related_name="achievement_awards"
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.PROTECT, related_name="awards")
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    world = models.ForeignKey(
        World, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # The attempt that triggered the award, used to tell the learner right after it.
    attempt = models.ForeignKey(
        ExerciseAttempt, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["awarded_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "achievement"], name="gamification_award_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.achievement} → {self.learner.user.get_username()}"


class BossChallenge(models.Model):
    """Marks an existing Exercise as a checkpoint challenge. Not a project.

    Prompt, evaluation and availability all stay with the Exercise and the normal curriculum.
    """

    exercise = models.OneToOneField(Exercise, on_delete=models.CASCADE, related_name="boss")
    bonus_xp = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(bonus_xp__gt=0), name="gamification_boss_bonus_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"Boss: {self.exercise.title}"


class BossCompletion(models.Model):
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="boss_completions"
    )
    boss = models.ForeignKey(BossChallenge, on_delete=models.PROTECT, related_name="completions")
    attempt = models.ForeignKey(
        ExerciseAttempt, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completed_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "boss"], name="gamification_boss_completion_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.boss} completed"
