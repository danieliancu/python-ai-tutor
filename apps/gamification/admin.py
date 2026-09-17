from django.contrib import admin

from apps.attempts.admin import ReadOnlyAdminMixin
from apps.gamification.levels import level_for_xp
from apps.gamification.models import (
    Achievement,
    AchievementAward,
    BossChallenge,
    BossCompletion,
    GamificationProfile,
    XPEvent,
)


@admin.register(GamificationProfile)
class GamificationProfileAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "learner",
        "total_xp",
        "level",
        "current_streak",
        "longest_streak",
        "last_activity_date",
        "updated_at",
    ]
    search_fields = ["learner__user__username", "learner__user__email"]
    list_select_related = ["learner__user"]

    @admin.display(description="Level")
    def level(self, obj: GamificationProfile) -> int:
        return level_for_xp(obj.total_xp)


@admin.register(XPEvent)
class XPEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["id", "learner", "world", "event_type", "xp", "source_key", "created_at"]
    list_filter = ["event_type", "world"]
    search_fields = ["learner__user__username", "source_key"]
    list_select_related = ["learner__user", "world"]
    raw_id_fields = ["learner", "enrollment", "attempt"]


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ["title", "code", "rarity", "is_active", "order"]
    list_filter = ["rarity", "is_active"]
    list_editable = ["is_active", "order"]
    search_fields = ["title", "code"]


@admin.register(AchievementAward)
class AchievementAwardAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["achievement", "learner", "world", "awarded_at"]
    list_filter = ["achievement", "world"]
    search_fields = ["learner__user__username"]
    list_select_related = ["achievement", "learner__user", "world"]
    raw_id_fields = ["learner", "enrollment", "attempt"]


@admin.register(BossChallenge)
class BossChallengeAdmin(admin.ModelAdmin):
    list_display = ["exercise", "bonus_xp", "is_active", "order"]
    list_filter = ["is_active", "exercise__lesson__concept__skill__world"]
    search_fields = ["exercise__title", "exercise__slug"]
    list_select_related = ["exercise"]
    raw_id_fields = ["exercise"]


@admin.register(BossCompletion)
class BossCompletionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["boss", "enrollment", "completed_at"]
    list_filter = ["boss"]
    list_select_related = ["boss__exercise", "enrollment__learner__user", "enrollment__world"]
    raw_id_fields = ["enrollment", "attempt"]
