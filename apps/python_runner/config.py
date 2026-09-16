from collections.abc import Mapping
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

BACKEND_DISABLED = "disabled"
BACKEND_DOCKER = "docker"
BACKENDS = (BACKEND_DISABLED, BACKEND_DOCKER)


@dataclass(frozen=True)
class RunnerConfig:
    backend: str = BACKEND_DISABLED
    image: str = "python:3.11-slim"
    timeout_seconds: float = 3.0
    memory_mb: int = 128
    cpus: float = 0.5
    pids_limit: int = 64
    max_output_bytes: int = 65536
    max_source_bytes: int = 65536
    docker_binary: str = "docker"

    @property
    def enabled(self) -> bool:
        return self.backend == BACKEND_DOCKER

    @classmethod
    def from_settings(cls, raw: Mapping[str, object]) -> "RunnerConfig":
        """Build a validated config from the ``PYTHON_RUNNER`` settings dictionary."""
        defaults = cls()

        def value(key: str, default: object) -> str:
            found = raw.get(key)
            return str(default if found in (None, "") else found).strip()

        backend = value("BACKEND", defaults.backend).lower()
        if backend not in BACKENDS:
            raise _error("BACKEND", f"must be one of {', '.join(BACKENDS)}, got {backend!r}")
        return cls(
            backend=backend,
            image=_word("IMAGE", value("IMAGE", defaults.image)),
            timeout_seconds=_number(
                "TIMEOUT_SECONDS", value("TIMEOUT_SECONDS", defaults.timeout_seconds), 0.1, 60
            ),
            memory_mb=int(
                _number("MEMORY_MB", value("MEMORY_MB", defaults.memory_mb), 32, 4096, True)
            ),
            cpus=_number("CPUS", value("CPUS", defaults.cpus), 0.05, 8),
            pids_limit=int(
                _number("PIDS_LIMIT", value("PIDS_LIMIT", defaults.pids_limit), 8, 4096, True)
            ),
            max_output_bytes=int(
                _number(
                    "MAX_OUTPUT_BYTES",
                    value("MAX_OUTPUT_BYTES", defaults.max_output_bytes),
                    1024,
                    16 * 1024 * 1024,
                    True,
                )
            ),
            max_source_bytes=int(
                _number(
                    "MAX_SOURCE_BYTES",
                    value("MAX_SOURCE_BYTES", defaults.max_source_bytes),
                    1024,
                    1024 * 1024,
                    True,
                )
            ),
            docker_binary=_word("DOCKER_BINARY", value("DOCKER_BINARY", defaults.docker_binary)),
        )


def _error(key: str, problem: str) -> ImproperlyConfigured:
    return ImproperlyConfigured(f"PYTHON_RUNNER_{key} {problem}.")


def _word(key: str, text: str) -> str:
    if not text or any(character.isspace() for character in text):
        raise _error(key, "must be a non-empty value without spaces")
    return text


def _number(key: str, text: str, low: float, high: float, integer: bool = False) -> float:
    try:
        number = int(text) if integer else float(text)
    except ValueError:
        kind = "a whole number" if integer else "a number"
        raise _error(key, f"must be {kind}, got {text!r}") from None
    if not low <= number <= high:
        raise _error(key, f"must be between {low:g} and {high:g}, got {text}")
    return number


def get_runner_config() -> RunnerConfig:
    return RunnerConfig.from_settings(settings.PYTHON_RUNNER)
