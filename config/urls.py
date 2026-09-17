from django.contrib import admin
from django.urls import include, path

from config import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.learners.urls")),
    path("app/", include("apps.attempts.urls")),
    path("app/", include("apps.learner_intelligence.urls")),
    path("app/", include("apps.next_action.urls")),
    path("app/", include("apps.ai_tutor.urls")),
    path("app/", include("apps.gamification.urls")),
    path("learn/", include("apps.course_player.urls")),
    path("learn/", include("apps.projects.urls")),
    path("admin/", admin.site.urls),
]
