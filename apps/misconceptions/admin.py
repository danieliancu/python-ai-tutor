from django.contrib import admin

from apps.attempts.admin import ReadOnlyAdminMixin
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState


@admin.register(MisconceptionState)
class MisconceptionStateAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Derived from attempts; rebuilt with ``rebuild_misconceptions``."""

    list_display = [
        "learner",
        "world",
        "skill",
        "concept",
        "code",
        "status",
        "confidence_score",
        "positive_evidence_count",
        "counter_evidence_count",
        "strong_evidence_count",
        "distinct_exercise_count",
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
        "algorithm_version",
    ]
    list_filter = ["enrollment__world", "status", "code"]
    list_select_related = ["enrollment__learner__user", "enrollment__world", "concept__skill"]
    search_fields = [
        "enrollment__learner__user__username",
        "enrollment__learner__user__email",
        "concept__title",
        "concept__skill__title",
        "code",
    ]

    @admin.display(description="Learner", ordering="enrollment__learner__user__username")
    def learner(self, obj: MisconceptionState) -> str:
        return obj.enrollment.learner.user.get_username()

    @admin.display(description="World", ordering="enrollment__world__title")
    def world(self, obj: MisconceptionState) -> str:
        return obj.enrollment.world.title

    @admin.display(description="Skill", ordering="concept__skill__title")
    def skill(self, obj: MisconceptionState) -> str:
        return obj.concept.skill.title


@admin.register(MisconceptionEvidence)
class MisconceptionEvidenceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Audit trail of detector signals. Shows no answers or exercise specs."""

    list_display = ["attempt_id", "learner", "exercise", "code", "kind", "strength", "source"]
    list_filter = ["kind", "source", "code"]
    list_select_related = ["attempt__enrollment__learner__user", "attempt__exercise"]
    search_fields = [
        "code",
        "source",
        "attempt__enrollment__learner__user__username",
        "attempt__enrollment__learner__user__email",
        "attempt__exercise__title",
    ]
    fields = ["attempt_id", "code", "kind", "strength", "source", "details", "created_at"]
    readonly_fields = fields

    @admin.display(description="Learner", ordering="attempt__enrollment__learner__user__username")
    def learner(self, obj: MisconceptionEvidence) -> str:
        return obj.attempt.enrollment.learner.user.get_username()

    @admin.display(description="Exercise", ordering="attempt__exercise__title")
    def exercise(self, obj: MisconceptionEvidence) -> str:
        return obj.attempt.exercise.title
