from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


@never_cache
@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: the process is up and serving requests. Does not query the database."""
    return JsonResponse({"status": "ok"})
