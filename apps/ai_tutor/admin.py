from django.contrib import admin

from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.attempts.admin import ReadOnlyAdminMixin


@admin.register(TutorTurn)
class TutorTurnAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Conversation log. Messages are only shown on the detail page, as plain text."""

    list_display = [
        "id",
        "learner",
        "world",
        "exercise",
        "requested_intent",
        "response_kind",
        "status",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "created_at",
    ]
    list_filter = ["status", "requested_intent", "response_kind", "model", "enrollment__world"]
    list_select_related = ["enrollment__learner__user", "enrollment__world", "exercise"]
    search_fields = [
        "enrollment__learner__user__username",
        "enrollment__learner__user__email",
        "exercise__title",
    ]
    date_hierarchy = "created_at"
    exclude = ["provider_response_id"]

    @admin.display(description="Learner", ordering="enrollment__learner__user__username")
    def learner(self, obj: TutorTurn) -> str:
        return obj.enrollment.learner.user.get_username()

    @admin.display(description="World", ordering="enrollment__world__title")
    def world(self, obj: TutorTurn) -> str:
        return obj.enrollment.world.title


@admin.register(TutorExerciseState)
class TutorExerciseStateAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Operational assistance state; changed only by tutor turns and new attempts."""

    list_display = [
        "enrollment",
        "exercise",
        "hint_level",
        "used_explanation",
        "used_solution",
        "last_attempt",
        "updated_at",
    ]
    list_select_related = ["enrollment__learner__user", "enrollment__world", "exercise"]
    search_fields = ["enrollment__learner__user__username", "exercise__title"]
