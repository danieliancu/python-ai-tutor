from django.contrib import admin

from apps.attempts.admin import ReadOnlyAdminMixin
from apps.projects.models import (
    Project,
    ProjectCompletion,
    ProjectConceptRequirement,
    ProjectDraft,
    ProjectStage,
    ProjectSubmission,
)

PRIVATE_SPEC = "Evaluation (private, never shown to learners or the AI tutor)"


class RequirementInline(admin.TabularInline):
    model = ProjectConceptRequirement
    extra = 0
    autocomplete_fields = ["concept"]


class StageInline(admin.StackedInline):
    model = ProjectStage
    extra = 0
    classes = ["collapse"]
    fieldsets = [
        (None, {"fields": ["order", "title", "slug", "is_published", "estimated_minutes"]}),
        ("Learner-facing content", {"fields": ["objective", "instructions", "requirements"]}),
        ("Starter code", {"fields": ["starter_code"]}),
        (PRIVATE_SPEC, {"fields": ["evaluation_spec"]}),
    ]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "world", "order", "difficulty", "xp_reward", "is_published"]
    list_filter = ["world", "difficulty", "is_published"]
    search_fields = ["title", "slug", "summary"]
    prepopulated_fields = {"slug": ["title"]}
    list_select_related = ["world"]
    inlines = [RequirementInline, StageInline]


@admin.register(ProjectConceptRequirement)
class ProjectConceptRequirementAdmin(admin.ModelAdmin):
    list_display = ["project", "concept", "minimum_mastery"]
    list_filter = ["project__world", "project"]
    list_select_related = ["project", "concept"]
    autocomplete_fields = ["concept"]


@admin.register(ProjectStage)
class ProjectStageAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "order", "estimated_minutes", "is_published"]
    list_filter = ["project__world", "project", "is_published"]
    search_fields = ["title", "slug", "project__title"]
    list_select_related = ["project"]
    fieldsets = StageInline.fieldsets[:1] + [
        (None, {"fields": ["project"]}),
        *StageInline.fieldsets[1:],
    ]


@admin.register(ProjectDraft)
class ProjectDraftAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["project", "enrollment", "current_stage", "updated_at"]
    list_filter = ["project"]
    search_fields = ["enrollment__learner__user__username"]
    list_select_related = ["project", "enrollment__learner__user", "enrollment__world"]


@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["id", "project", "stage", "enrollment", "attempt_number", "status"]
    list_filter = ["status", "project"]
    search_fields = ["enrollment__learner__user__username"]
    list_select_related = ["project", "stage", "enrollment__learner__user", "enrollment__world"]


@admin.register(ProjectCompletion)
class ProjectCompletionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["project", "enrollment", "completed_at"]
    list_filter = ["project"]
    list_select_related = ["project", "enrollment__learner__user", "enrollment__world"]
