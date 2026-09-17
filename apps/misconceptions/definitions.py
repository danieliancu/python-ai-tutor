"""What a misconception means. Definitions hold no learner state.

Domain packages register their catalogs here; the engine only looks codes up.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

SAFE_CODE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
MAX_CODE_LENGTH = 64


def is_safe_code(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_CODE_LENGTH
        and bool(SAFE_CODE.fullmatch(value))
    )


@dataclass(frozen=True)
class MisconceptionDefinition:
    code: str
    title: str
    description: str
    domain: str
    category: str | None = None


_DEFINITIONS: dict[str, MisconceptionDefinition] = {}


def register_definitions(definitions: Iterable[MisconceptionDefinition]) -> None:
    """Add a catalog. Codes are global, so a code can only be defined once."""
    for definition in definitions:
        if not is_safe_code(definition.code):
            raise ValueError(f"Unsafe misconception code: {definition.code!r}")
        existing = _DEFINITIONS.get(definition.code)
        if existing is not None and existing != definition:
            raise ValueError(f"Misconception {definition.code!r} is already defined.")
        _DEFINITIONS[definition.code] = definition


def get_definition(code: str) -> MisconceptionDefinition | None:
    return _DEFINITIONS.get(code)


def all_definitions() -> dict[str, MisconceptionDefinition]:
    return dict(_DEFINITIONS)


def title_for(code: str) -> str:
    """The registered title, or a readable fallback for codes without a catalog entry."""
    definition = get_definition(code)
    if definition is not None:
        return definition.title
    return code.replace("-", " ").replace("_", " ").capitalize()
