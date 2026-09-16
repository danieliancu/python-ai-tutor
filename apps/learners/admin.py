from django.contrib import admin

from apps.learners.models import Enrollment, LearnerProfile


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ["world"]
    readonly_fields = ["enrolled_at", "updated_at"]


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "preferred_name", "onboarding_completed_at", "created_at"]
    list_filter = [("onboarding_completed_at", admin.EmptyFieldListFilter), "timezone"]
    list_select_related = ["user"]
    search_fields = ["user__username", "user__email", "preferred_name"]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [EnrollmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["learner", "world", "status", "enrolled_at"]
    list_filter = ["status", "world"]
    list_select_related = ["learner__user", "world"]
    search_fields = ["learner__user__username", "learner__user__email", "world__title"]
    autocomplete_fields = ["learner", "world"]
    readonly_fields = ["enrolled_at", "updated_at"]
