from django.contrib import admin

from apps.attempts.admin import ReadOnlyAdminMixin
from apps.learner_intelligence.models import ConceptModeState, ConceptState

MODE_FIELDS = [
    "learning_mode",
    "performance_score",
    "attempt_count",
    "correct_count",
    "independence_score",
    "fluency_score",
    "last_attempt_at",
    "updated_at",
]


class ConceptModeStateInline(ReadOnlyAdminMixin, admin.TabularInline):
    """Derived from attempts; rebuilt with ``rebuild_learner_intelligence``."""

    model = ConceptModeState
    extra = 0
    can_delete = False
    fields = MODE_FIELDS
    readonly_fields = MODE_FIELDS


@admin.register(ConceptState)
class ConceptStateAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "learner",
        "world",
        "skill",
        "concept",
        "mastery_score",
        "mastery_band",
        "retention_score",
        "independence_score",
        "fluency_score",
        "trend",
        "stability_days",
        "review_due_at",
        "evidence_count",
        "correct_count",
        "updated_at",
    ]
    list_filter = ["enrollment__world", "mastery_band", "trend", "review_due_at"]
    list_select_related = ["enrollment__learner__user", "enrollment__world", "concept__skill"]
    search_fields = [
        "enrollment__learner__user__username",
        "enrollment__learner__user__email",
        "concept__title",
        "concept__skill__title",
        "enrollment__world__title",
    ]
    inlines = [ConceptModeStateInline]

    @admin.display(description="Learner", ordering="enrollment__learner__user__username")
    def learner(self, obj: ConceptState) -> str:
        return obj.enrollment.learner.user.get_username()

    @admin.display(description="World", ordering="enrollment__world__title")
    def world(self, obj: ConceptState) -> str:
        return obj.enrollment.world.title

    @admin.display(description="Skill", ordering="concept__skill__title")
    def skill(self, obj: ConceptState) -> str:
        return obj.concept.skill.title


@admin.register(ConceptModeState)
class ConceptModeStateAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["concept_state", *MODE_FIELDS]
    list_filter = ["learning_mode"]
    list_select_related = [
        "concept_state__enrollment__learner__user",
        "concept_state__enrollment__world",
        "concept_state__concept",
    ]
    search_fields = [
        "concept_state__enrollment__learner__user__username",
        "concept_state__concept__title",
    ]
