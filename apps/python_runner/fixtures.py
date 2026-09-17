"""Private data files that a run may place in the sandbox (for example a CSV to read).

Fixture files are author-provided, never learner-provided. They are copied into the
container's writable working directory (the ephemeral /tmp tmpfs) before the program starts,
so learner code opens them with plain relative names such as ``open("data.csv")``.
"""

import re

FIXTURE_DIR = "fixtures"
MAX_FIXTURE_FILES = 8
MAX_FIXTURE_BYTES = 256 * 1024
MAX_FIXTURE_NAME = 64
# One plain file name: letters, digits, "_" and "-", with optional dot-separated extensions.
FIXTURE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*$")
RESERVED_NAMES = frozenset({"learner.py", "harness.py", "bootstrap.py"})


class FixtureRejected(ValueError):
    """Fixture files that must never reach the sandbox."""


def is_safe_fixture_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and 0 < len(name) <= MAX_FIXTURE_NAME
        and FIXTURE_NAME.match(name) is not None
        and name.lower() not in RESERVED_NAMES
    )


def validate_fixture_files(files: object) -> dict[str, str]:
    """The fixtures as a {name: text} dict, or FixtureRejected. No paths, no binary data."""
    if not isinstance(files, dict):
        raise FixtureRejected("Fixture files must be an object of file name to text.")
    if len(files) > MAX_FIXTURE_FILES:
        raise FixtureRejected(f"At most {MAX_FIXTURE_FILES} fixture files are allowed.")
    total = 0
    for name, text in files.items():
        if not is_safe_fixture_name(name):
            raise FixtureRejected(f"Unsafe fixture file name: {name!r}.")
        if not isinstance(text, str) or "\x00" in text:
            raise FixtureRejected(f"Fixture {name!r} must be UTF-8 text.")
        try:
            total += len(text.encode("utf-8"))
        except UnicodeEncodeError:
            raise FixtureRejected(f"Fixture {name!r} must be UTF-8 text.") from None
    if total > MAX_FIXTURE_BYTES:
        raise FixtureRejected(f"Fixture files are limited to {MAX_FIXTURE_BYTES} bytes in total.")
    return dict(files)
