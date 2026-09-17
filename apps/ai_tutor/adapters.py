"""Extension point for domain-specific tutoring (e.g. a future per-language adapter).

Adapters may add trusted instructions, private teaching context and reply post-processing.
Phase 8 ships only the generic adapter; nothing dispatches on World slugs.
"""

from typing import Protocol


class TutorDomainAdapter(Protocol):
    name: str

    def applies_to(self, world) -> bool: ...

    def extra_instructions(self, server_context: dict) -> str: ...

    def private_teaching_context(self, *, enrollment, exercise, latest_attempt) -> dict: ...

    def postprocess_reply(self, reply: str) -> str: ...


class GenericTutorAdapter:
    """Domain-neutral behaviour: no extra instructions and no private context."""

    name = "generic"

    def applies_to(self, world) -> bool:
        return True

    def extra_instructions(self, server_context: dict) -> str:
        return ""

    def private_teaching_context(self, *, enrollment, exercise, latest_attempt) -> dict:
        return {}

    def postprocess_reply(self, reply: str) -> str:
        return reply.strip()


# Domain adapters are registered ahead of the generic fallback.
ADAPTERS: list[TutorDomainAdapter] = []
FALLBACK = GenericTutorAdapter()


def adapter_for(world) -> TutorDomainAdapter:
    for adapter in ADAPTERS:
        if adapter.applies_to(world):
            return adapter
    return FALLBACK
