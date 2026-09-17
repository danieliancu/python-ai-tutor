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
    path("admin/", admin.site.urls),
]
