from django.urls import path

from apps.ai_tutor import views

app_name = "ai_tutor"

urlpatterns = [
    path("worlds/<int:world_id>/tutor/turns/", views.tutor_turns, name="turns"),
]
