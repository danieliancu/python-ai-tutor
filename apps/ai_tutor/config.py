"""Validated AI tutor settings (``settings.AI_TUTOR``)."""

from collections.abc import Mapping
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_MODEL = "gpt-5.6-luna"


@dataclass(frozen=True)
class TutorConfig:
    enabled: bool = False
    api_key: str = ""
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 20.0
    history_turns: int = 8
    max_user_chars: int = 4000
    max_output_tokens: int = 800
    rate_limit_per_minute: int = 20

    @property
    def available(self) -> bool:
        """Whether tutor requests may reach the provider at all."""
        return self.enabled and bool(self.api_key)

    def __repr__(self) -> str:  # never print the key
        return f"TutorConfig(enabled={self.enabled}, model={self.model!r})"

    @classmethod
    def from_settings(cls, raw: Mapping[str, object]) -> "TutorConfig":
        defaults = cls()

        def value(key: str, default: object) -> str:
            found = raw.get(key)
            return str(default if found in (None, "") else found).strip()

        enabled = raw.get("ENABLED", defaults.enabled)
        if not isinstance(enabled, bool):
            raise _error("ENABLED", "must be a boolean")
        model = value("OPENAI_MODEL", defaults.model)
        if not model or any(ch.isspace() for ch in model):
            raise _error("OPENAI_MODEL", f"must be a model name, got {model!r}")
        return cls(
            enabled=enabled,
            api_key=str(raw.get("OPENAI_API_KEY") or "").strip(),
            model=model,
            timeout_seconds=_number(
                "OPENAI_TIMEOUT_SECONDS",
                value("OPENAI_TIMEOUT_SECONDS", defaults.timeout_seconds),
                1,
                300,
            ),
            history_turns=_integer(
                "HISTORY_TURNS", value("HISTORY_TURNS", defaults.history_turns), 0, 50
            ),
            max_user_chars=_integer(
                "MAX_USER_CHARS", value("MAX_USER_CHARS", defaults.max_user_chars), 1, 20_000
            ),
            max_output_tokens=_integer(
                "MAX_OUTPUT_TOKENS",
                value("MAX_OUTPUT_TOKENS", defaults.max_output_tokens),
                16,
                8_000,
            ),
            rate_limit_per_minute=_integer(
                "RATE_LIMIT_PER_MINUTE",
                value("RATE_LIMIT_PER_MINUTE", defaults.rate_limit_per_minute),
                1,
                1_000,
            ),
        )


def _error(key: str, problem: str) -> ImproperlyConfigured:
    return ImproperlyConfigured(f"AI_TUTOR[{key!r}] {problem}.")


def _number(key: str, raw: str, low: float, high: float) -> float:
    try:
        number = float(raw)
    except ValueError:
        raise _error(key, f"must be a number, got {raw!r}") from None
    if not low <= number <= high:
        raise _error(key, f"must be between {low} and {high}, got {raw!r}")
    return number


def _integer(key: str, raw: str, low: int, high: int) -> int:
    try:
        number = int(raw)
    except ValueError:
        raise _error(key, f"must be a whole number, got {raw!r}") from None
    if not low <= number <= high:
        raise _error(key, f"must be between {low} and {high}, got {raw!r}")
    return number


def get_tutor_config() -> TutorConfig:
    return TutorConfig.from_settings(getattr(settings, "AI_TUTOR", {}))
