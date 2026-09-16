from django.contrib import admin

from apps.curriculum.admin import LessonAdmin
from apps.curriculum.models import Lesson
from apps.exercises.models import Exercise


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["title", "lesson", "response_type", "learning_mode", "order", "is_published"]
    list_filter = [
        "response_type",
        "learning_mode",
        "is_published",
        "lesson__concept__skill__world",
    ]
    list_select_related = ["lesson"]
    search_fields = ["title", "slug", "prompt", "lesson__title", "lesson__concept__title"]
    autocomplete_fields = ["lesson"]
    prepopulated_fields = {"slug": ["title"]}
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "lesson",
                    "title",
                    "slug",
                    "order",
                    "response_type",
                    "learning_mode",
                    "target_seconds",
                    "is_published",
                ]
            },
        ),
        ("Learner-facing content", {"fields": ["prompt", "instructions", "content"]}),
        (
            "Evaluation (private, never shown to learners)",
            {"fields": ["evaluation_spec"]},
        ),
    ]


class ExerciseInline(admin.TabularInline):
    """Read-only overview on the Lesson page. Exercises are created and edited on their own
    page, which has room for the prompt, content and evaluation spec."""

    model = Exercise
    extra = 0
    fields = ["title", "order", "response_type", "learning_mode", "is_published"]
    readonly_fields = fields
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


# Add the inline from this app so the curriculum app doesn't depend on exercises.
admin.site.unregister(Lesson)


@admin.register(Lesson)
class LessonWithExercisesAdmin(LessonAdmin):
    inlines = [*LessonAdmin.inlines, ExerciseInline]
