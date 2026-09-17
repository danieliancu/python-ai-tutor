from django.urls import path

from apps.course_player import views

app_name = "course_player"

urlpatterns = [
    path("worlds/<int:world_id>/", views.world, name="world"),
    path("worlds/<int:world_id>/progress/", views.progress, name="progress"),
]
