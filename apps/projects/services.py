"""Saving drafts and checking project stages. The one place project work is recorded."""

import logging
from dataclasses import dataclass
from importlib import import_module

from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.attempts.models import MAX_DURATION_SECONDS, AttemptStatus
from apps.evaluation.exceptions import EvaluationError
from apps.learners.models import Enrollment
from apps.projects import selectors
from apps.projects.evaluation import evaluator_for
from apps.projects.models import (
    Project,
    ProjectCompletion,
    ProjectDraft,
    ProjectStage,
    ProjectSubmission,
)
from apps.python_runner.config import get_runner_config

logger = logging.getLogger(__name__)

NUMBERING_RETRIES = 3
UNAVAILABLE_MESSAGE = "We couldn't check your project right now. Your code is saved."
SAFE_DIAGNOSTIC_KEYS = ("reason", "error_type", "missing")


class ProjectRequestError(Exception):
    def __init__(self, code: str, status: int) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class SubmissionOutcome:
    submission: ProjectSubmission
    stage_completed: bool
    project_completed: bool
    next_stage: ProjectStage | None


def _safe_identifier(value: object) -> bool:
    return (
        isinstance(value, str) and 0 < len(value) <= 64 and value.replace(".", "_").isidentifier()
    )


def safe_project_diagnostics(diagnostics) -> dict:
    return {
        key: diagnostics[key]
        for key in SAFE_DIAGNOSTIC_KEYS
        if key in diagnostics and _safe_identifier(diagnostics[key])
    }


def validate_project_source(source: object) -> str:
    if not isinstance(source, str) or "\x00" in source:
        raise ProjectRequestError("invalid_source", 400)
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        raise ProjectRequestError("invalid_source", 400) from None
    if size > get_runner_config().max_source_bytes:
        raise ProjectRequestError("source_too_large", 400)
    return source


def _usable_stage(enrollment: Enrollment, project: Project, stage: ProjectStage):
    view = selectors.project_view(enrollment, project)
    if not view.unlocked:
        raise ProjectRequestError("project_locked", 409)
    item = selectors.stage_view(view, stage)
    if item is None or not item.available:
        raise ProjectRequestError("stage_locked", 409)
    return view, item


def save_draft(
    enrollment: Enrollment, project: Project, stage: ProjectStage, source: object
) -> ProjectDraft:
    source = validate_project_source(source)
    _usable_stage(enrollment, project, stage)
    draft, _ = ProjectDraft.objects.update_or_create(
        enrollment=enrollment,
        project=project,
        defaults={"source_code": source, "current_stage": stage},
    )
    return draft


def _evaluate(project: Project, stage: ProjectStage, source: str) -> dict:
    evaluator = evaluator_for(project.world.domain)
    try:
        result = evaluator.evaluate(stage.evaluation_spec, source)
    except EvaluationError as exc:
        logger.error("Could not check stage %s of project %s: %s", stage.pk, project.pk, exc)
        return {
            "status": AttemptStatus.UNAVAILABLE,
            "score": None,
            "is_correct": None,
            "evaluator": getattr(evaluator, "name", "unknown"),
            "message": UNAVAILABLE_MESSAGE,
            "diagnostics": {"reason": "evaluation_unavailable"},
        }
    return {
        "status": AttemptStatus(str(result.status)),
        "score": result.score,
        "is_correct": result.is_correct,
        "evaluator": result.evaluator,
        "message": result.message[:300],
        "diagnostics": safe_project_diagnostics(result.diagnostics),
    }


def _store(enrollment, project, stage, snapshot, source, duration_seconds) -> ProjectSubmission:
    for retry in range(NUMBERING_RETRIES):
        try:
            with transaction.atomic():
                Enrollment.objects.select_for_update().filter(pk=enrollment.pk).first()
                last = ProjectSubmission.objects.filter(
                    enrollment=enrollment, stage=stage
                ).aggregate(last=Max("attempt_number"))["last"]
                return ProjectSubmission.objects.create(
                    enrollment=enrollment,
                    project=project,
                    stage=stage,
                    attempt_number=(last or 0) + 1,
                    submitted_source=source,
                    duration_seconds=duration_seconds,
                    **snapshot,
                )
        except IntegrityError:
            if retry == NUMBERING_RETRIES - 1:
                raise
    raise AssertionError("unreachable")


def complete_if_finished(
    enrollment: Enrollment, project: Project, submission: ProjectSubmission
) -> bool:
    """Create the completion once every published stage has passed. Safe to repeat."""
    view = selectors.project_view(enrollment, project)
    if not view.stages or not all(stage.done for stage in view.stages):
        return False
    try:
        with transaction.atomic():
            ProjectCompletion.objects.get_or_create(
                enrollment=enrollment, project=project, defaults={"final_submission": submission}
            )
    except IntegrityError:
        # A simultaneous final submission completed the project first.
        pass
    return True


def _validate_duration(duration_seconds: object) -> int | None:
    if duration_seconds is None:
        return None
    if (
        not isinstance(duration_seconds, int)
        or isinstance(duration_seconds, bool)
        or not 0 <= duration_seconds <= MAX_DURATION_SECONDS
    ):
        raise ProjectRequestError("invalid_duration", 400)
    return duration_seconds


def submit_stage(
    enrollment: Enrollment,
    project: Project,
    stage: ProjectStage,
    source: object,
    duration_seconds: object = None,
) -> SubmissionOutcome:
    duration = _validate_duration(duration_seconds)
    # The learner's code is saved before anything can fail.
    save_draft(enrollment, project, stage, source)
    # Checking may take seconds: never hold database locks while it runs.
    snapshot = _evaluate(project, stage, source)
    submission = _store(enrollment, project, stage, snapshot, source, duration)

    stage_completed = submission.status == AttemptStatus.CORRECT and submission.is_correct is True
    project_completed = False
    if stage_completed:
        project_completed = complete_if_finished(enrollment, project, submission)
    _refresh_derived_state(submission)

    next_stage = None
    if stage_completed:
        view = selectors.project_view(enrollment, project)
        item = selectors.stage_view(view, stage)
        if item is not None and item.number < view.total:
            next_stage = view.stages[item.number].stage
    return SubmissionOutcome(submission, stage_completed, project_completed, next_stage)


# Recoverable work after a stored submission (rebuild_gamification repairs it).
POST_SUBMISSION_STEPS = (
    (
        "Gamification",
        "apps.gamification.services",
        "refresh_for_project_submission",
        "run rebuild_gamification to recover",
    ),
)


def _refresh_derived_state(submission: ProjectSubmission) -> None:
    for label, module_path, function, recovery in POST_SUBMISSION_STEPS:
        try:
            getattr(import_module(module_path), function)(submission)
        except Exception:
            logger.exception(
                "%s refresh failed for project submission %s; %s.", label, submission.pk, recovery
            )
