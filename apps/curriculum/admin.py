from django.contrib import admin

from apps.curriculum.models import (
    Concept,
    ConceptPrerequisite,
    Lesson,
    Skill,
    SkillPrerequisite,
    World,
)


@admin.register(World)
class WorldAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "order", "is_published"]
    list_filter = ["is_published"]
    search_fields = ["title", "slug"]
    ordering = ["order", "id"]
    prepopulated_fields = {"slug": ["title"]}


class SkillPrerequisiteInline(admin.TabularInline):
    model = SkillPrerequisite
    fk_name = "skill"
    extra = 0
    autocomplete_fields = ["prerequisite"]
    verbose_name = "prerequisite"
    verbose_name_plural = "prerequisites"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["title", "world", "order", "is_published"]
    list_filter = ["world", "is_published"]
    list_select_related = ["world"]
    search_fields = ["title", "slug"]
    ordering = ["world__order", "order", "id"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [SkillPrerequisiteInline]


@admin.register(SkillPrerequisite)
class SkillPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ["skill", "prerequisite"]
    list_filter = ["skill__world"]
    list_select_related = ["skill__world", "prerequisite__world"]
    search_fields = ["skill__title", "prerequisite__title"]
    autocomplete_fields = ["skill", "prerequisite"]
    ordering = ["skill__world__order", "skill__order", "prerequisite__order"]


class ConceptPrerequisiteInline(admin.TabularInline):
    model = ConceptPrerequisite
    fk_name = "concept"
    extra = 0
    autocomplete_fields = ["prerequisite"]
    verbose_name = "prerequisite"
    verbose_name_plural = "prerequisites"


@admin.register(Concept)
class ConceptAdmin(admin.ModelAdmin):
    list_display = ["title", "skill", "order", "is_published"]
    list_filter = ["skill__world", "skill", "is_published"]
    list_select_related = ["skill__world"]
    search_fields = ["title", "slug", "learning_objective"]
    ordering = ["skill__world__order", "skill__order", "order", "id"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [ConceptPrerequisiteInline]


@admin.register(ConceptPrerequisite)
class ConceptPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ["concept", "prerequisite"]
    list_filter = ["concept__skill__world", "concept__skill"]
    list_select_related = ["concept__skill", "prerequisite__skill"]
    search_fields = ["concept__title", "prerequisite__title"]
    autocomplete_fields = ["concept", "prerequisite"]
    ordering = ["concept__skill__order", "concept__order", "prerequisite__order"]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["title", "concept", "kind", "estimated_minutes", "order", "is_published"]
    list_filter = ["kind", "is_published", "concept__skill"]
    list_select_related = ["concept__skill"]
    search_fields = ["title", "slug", "objective", "concept__title"]
    ordering = ["concept__skill__world__order", "concept__skill__order", "concept__order", "order"]
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["concept"]
