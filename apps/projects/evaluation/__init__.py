"""Project stage evaluation, chosen by the World's domain. Always deterministic, never AI."""

from typing import Protocol

from apps.evaluation import results
from apps.evaluation.results import EvaluationResult


class ProjectEvaluator(Protocol):
    name: str

    def evaluate(self, spec: dict, source: object) -> EvaluationResult: ...


class UnsupportedProjectEvaluator:
    name = "unsupported_project"

    def evaluate(self, spec: dict, source: object) -> EvaluationResult:
        return results.unsupported(
            self.name, "no_project_evaluator", "Project checking is not available yet."
        )


def evaluator_for(domain: str) -> ProjectEvaluator:
    if domain == "python":
        # Imported lazily so tests can patch the class and settings are read per call.
        from apps.projects.evaluation.python import PythonProjectEvaluator

        return PythonProjectEvaluator()
    return UnsupportedProjectEvaluator()
