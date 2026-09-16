from django.urls import path

from apps.learners import views

app_name = "learners"

urlpatterns = [
    path("onboarding/", views.onboarding, name="onboarding"),
    path("profile/", views.profile, name="profile"),
]
