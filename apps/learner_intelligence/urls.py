from django.urls import path

from apps.learner_intelligence import views

app_name = "learner_intelligence"

urlpatterns = [
    path(
        "worlds/<int:world_id>/learning-state/",
        views.learning_state,
        name="learning_state",
    ),
]
