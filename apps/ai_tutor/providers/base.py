"""The provider contract. The tutor engine never touches a vendor SDK directly."""

from typing import Protocol

from apps.ai_tutor.constants import (
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMITED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
)
from apps.ai_tutor.types import TutorProviderRequest, TutorProviderResult


class TutorError(Exception):
    """A safe provider failure. Messages never include request data or vendor text."""

    code = PROVIDER_UNAVAILABLE


class TutorUnavailable(TutorError):
    code = PROVIDER_UNAVAILABLE


class TutorTimeout(TutorError):
    code = PROVIDER_TIMEOUT


class TutorRateLimited(TutorError):
    code = PROVIDER_RATE_LIMITED


class TutorInvalidResponse(TutorError):
    code = PROVIDER_INVALID_RESPONSE


class TutorProvider(Protocol):
    name: str

    def generate(self, request: TutorProviderRequest) -> TutorProviderResult: ...
