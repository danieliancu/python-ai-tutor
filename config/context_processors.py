"""Template context shared by every page."""

from django.conf import settings
from django.http import HttpRequest


def product(request: HttpRequest) -> dict:
    """The platform identity (cursuri.net), kept in one setting."""
    return {"product_name": settings.PRODUCT_NAME}
