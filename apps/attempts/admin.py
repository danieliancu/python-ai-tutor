from django.contrib import admin

from apps.attempts.models import AttemptMistake, ExerciseAttempt


class ReadOnlyAdminMixin:
    """Attempts are a historical record: viewable and deletable, never edited or added."""

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class AttemptMistakeInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = AttemptMistake
    extra = 0
    can_delete = False
    fields = ["code", "details"]
    readonly_fields = fields


@admin.register(ExerciseAttempt)
class ExerciseAttemptAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "enrollment",
        "exercise",
        "status",
        "score",
        "is_correct",
        "evaluator",
        "attempt_number",
        "submitted_at",
    ]
    list_filter = ["status", "is_correct", "evaluator", "exercise__lesson__concept__skill__world"]
    list_select_related = ["enrollment__learner__user", "enrollment__world", "exercise__lesson"]
    search_fields = [
        "exercise__title",
        "exercise__slug",
        "enrollment__learner__user__username",
        "enrollment__learner__user__email",
        "message",
    ]
    date_hierarchy = "submitted_at"
    inlines = [AttemptMistakeInline]


@admin.register(AttemptMistake)
class AttemptMistakeAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["code", "attempt", "learner", "exercise", "submitted_at"]
    list_filter = ["code"]
    list_select_related = [
        "attempt__enrollment__learner__user",
        "attempt__enrollment__world",
        "attempt__exercise__lesson",
    ]
    search_fields = [
        "code",
        "attempt__exercise__title",
        "attempt__enrollment__learner__user__username",
        "attempt__enrollment__learner__user__email",
    ]

    @admin.display(description="Learner", ordering="attempt__enrollment__learner__user__username")
    def learner(self, obj: AttemptMistake) -> str:
        return obj.attempt.enrollment.learner.user.get_username()

    @admin.display(description="Exercise")
    def exercise(self, obj: AttemptMistake) -> str:
        return obj.attempt.exercise.title

    @admin.display(description="Submitted at", ordering="attempt__submitted_at")
    def submitted_at(self, obj: AttemptMistake):
        return obj.attempt.submitted_at
