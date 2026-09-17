"""Extension point for domain-specific tutoring, selected by ``World.domain``.

Adapters may add trusted instructions, private teaching context (which must respect the
granted help level) and reply validation. Unknown domains get the generic adapter.
"""

from typing import Protocol

GENERAL_DOMAIN = "general"


class TutorDomainAdapter(Protocol):
    domain: str

    def extra_instructions(self, *, server_context: dict, granted: str, exercise) -> str: ...

    def private_teaching_context(
        self,
        *,
        enrollment,
        exercise,
        latest_attempt,
        granted: str,
        assistance,
        server_context: dict,
    ) -> dict: ...

    def validate_reply(self, reply: str, *, granted: str, exercise, private_context: dict) -> None:
        """Raise ``TutorInvalidResponse`` to reject a reply before anything is stored."""

    def postprocess_reply(self, reply: str) -> str: ...


class GenericTutorAdapter:
    """Domain-neutral behaviour: no extra instructions, no private context, no extra checks."""

    domain = GENERAL_DOMAIN

    def extra_instructions(self, *, server_context: dict, granted: str, exercise) -> str:
        return ""

    def private_teaching_context(
        self,
        *,
        enrollment,
        exercise,
        latest_attempt,
        granted: str,
        assistance,
        server_context: dict,
    ) -> dict:
        return {}

    def validate_reply(self, reply: str, *, granted: str, exercise, private_context: dict) -> None:
        return None

    def postprocess_reply(self, reply: str) -> str:
        return reply.strip()


FALLBACK = GenericTutorAdapter()
_ADAPTERS: dict[str, TutorDomainAdapter] = {}


def register_adapter(adapter: TutorDomainAdapter) -> None:
    existing = _ADAPTERS.get(adapter.domain)
    if existing is not None and type(existing) is not type(adapter):
        raise ValueError(f"A tutor adapter for domain {adapter.domain!r} is already registered.")
    _ADAPTERS[adapter.domain] = adapter


def adapter_for(world) -> TutorDomainAdapter:
    return _ADAPTERS.get(getattr(world, "domain", GENERAL_DOMAIN), FALLBACK)
