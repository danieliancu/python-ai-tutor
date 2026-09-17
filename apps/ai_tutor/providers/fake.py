"""A deterministic in-memory provider for tests and local development. No network."""

from apps.ai_tutor.types import TutorProviderRequest, TutorProviderResult


class FakeTutorProvider:
    name = "fake"

    def __init__(self, *, reply: str = "Let's look at this together.", kind=None, error=None):
        self.reply = reply
        self.kind = kind  # None: echo the granted kind
        self.error = error
        self.requests: list[TutorProviderRequest] = []

    def generate(self, request: TutorProviderRequest) -> TutorProviderResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        kind = self.kind or request.response_kind
        return TutorProviderResult(
            reply=f"{self.reply} ({kind})",
            response_kind=kind,
            should_retry=kind in {"hint", "strong_hint", "explanation"},
            provider=self.name,
            model="fake-model",
            provider_response_id="fake-response",
            input_tokens=120,
            output_tokens=30,
        )
