"""Detector registry: the generic detector plus every domain package.

A domain package exposes ``DEFINITIONS`` (misconception catalog) and ``DETECTORS``. Adding a
domain means adding its module path here; the engine itself never changes. Domain detectors
decide applicability themselves from exercise tags and capabilities (e.g. code language).
"""

from functools import cache
from importlib import import_module

from apps.misconceptions.definitions import register_definitions
from apps.misconceptions.evidence import Detector, GenericTagDetector

DOMAIN_PACKAGES = ("apps.misconceptions.domains.python",)


@cache
def _domains() -> tuple:
    modules = tuple(import_module(path) for path in DOMAIN_PACKAGES)
    for module in modules:
        register_definitions(module.DEFINITIONS)
    return modules


def load_domains() -> None:
    _domains()


def detectors() -> tuple[Detector, ...]:
    return (GenericTagDetector(), *(d for module in _domains() for d in module.DETECTORS))
