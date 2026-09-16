from django.urls import path

from apps.attempts import views

app_name = "attempts"

urlpatterns = [
    path(
        "exercises/<int:exercise_id>/attempts/",
        views.exercise_attempts,
        name="exercise_attempts",
    ),
    path("attempts/<int:attempt_id>/", views.attempt_detail_view, name="attempt_detail"),
]
