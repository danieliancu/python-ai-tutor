from django.contrib import admin
from django.urls import include, path

from config import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("accounts/", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
]
