from django.urls import path

from apps.gamification import views

app_name = "gamification"

urlpatterns = [
    path("gamification/summary/", views.summary, name="summary"),
]
