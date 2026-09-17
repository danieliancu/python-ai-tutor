from django.urls import path

from apps.next_action import views

app_name = "next_action"

urlpatterns = [
    path("worlds/<int:world_id>/next-action/", views.next_action, name="next_action"),
]
