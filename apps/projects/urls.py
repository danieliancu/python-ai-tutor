from django.urls import path

from apps.projects import views

app_name = "projects"

PROJECT = "worlds/<int:world_id>/projects/<slug:project_slug>/"

urlpatterns = [
    path("worlds/<int:world_id>/projects/", views.project_list, name="list"),
    path(PROJECT, views.project_detail, name="detail"),
    path(PROJECT + "draft/", views.draft, name="draft"),
    path(PROJECT + "stages/<slug:stage_slug>/", views.project_stage, name="stage"),
    path(PROJECT + "stages/<slug:stage_slug>/submit/", views.submit, name="submit"),
    path(PROJECT + "stages/<slug:stage_slug>/coach/", views.coach_turn, name="coach"),
]
