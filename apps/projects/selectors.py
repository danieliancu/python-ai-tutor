"""Server-side project state for one learner. Read-only.

Availability comes only from concept mastery (Learner Intelligence), never from XP, levels,
streaks or achievements.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Prefetch

from apps.attempts.models import AttemptStatus
from apps.learner_intelligence.models import ConceptState
from apps.learners.models import Enrollment
from apps.projects.models import (
    Project,
    ProjectCompletion,
    ProjectConceptRequirement,
    ProjectDraft,
    ProjectStage,
    ProjectSubmission,
)

LOCKED = "locked"
AVAILABLE = "available"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
STATE_LABELS = {
    LOCKED: "Locked",
    AVAILABLE: "Available",
    IN_PROGRESS: "In progress",
    COMPLETED: "Completed",
}


def published_projects(world_id: int):
    return Project.objects.filter(
        world_id=world_id, is_published=True, world__is_published=True
    ).order_by("order", "id")


def published_stages(project: Project) -> list[ProjectStage]:
    return list(project.stages.filter(is_published=True).order_by("order", "id"))


@dataclass
class RequirementView:
    concept: str
    skill: str
    required: int
    current: int

    @property
    def met(self) -> bool:
        return self.current >= self.required


@dataclass
class StageView:
    stage: ProjectStage
    number: int
    done: bool
    available: bool
    current: bool = False

    @property
    def state(self) -> str:
        if self.done:
            return "done"
        return "available" if self.available else "locked"


@dataclass
class ProjectView:
    project: Project
    state: str
    requirements: list[RequirementView]
    stages: list[StageView]
    completion: ProjectCompletion | None = None
    started: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return STATE_LABELS[self.state]

    @property
    def unlocked(self) -> bool:
        return self.state != LOCKED

    @property
    def done_count(self) -> int:
        return sum(stage.done for stage in self.stages)

    @property
    def total(self) -> int:
        return len(self.stages)

    @property
    def percent(self) -> int:
        return round(100 * self.done_count / self.total) if self.total else 0

    @property
    def current_stage(self) -> StageView | None:
        return next((stage for stage in self.stages if stage.current), None)

    @property
    def missing_requirements(self) -> list[RequirementView]:
        return [requirement for requirement in self.requirements if not requirement.met]


def _mastery_map(enrollment: Enrollment) -> dict[int, int]:
    return {
        concept_id: int(Decimal(score))
        for concept_id, score in ConceptState.objects.filter(enrollment=enrollment).values_list(
            "concept_id", "mastery_score"
        )
    }


def _stage_views(stages: list[ProjectStage], done_ids: set[int]) -> list[StageView]:
    views = []
    previous_done = True
    for number, stage in enumerate(stages, start=1):
        done = stage.pk in done_ids
        views.append(StageView(stage, number, done=done, available=previous_done))
        previous_done = previous_done and done
    current = next((view for view in views if view.available and not view.done), None)
    if current is not None:
        current.current = True
    return views


def _build(project, enrollment, mastery, done_ids, started_ids, completions) -> ProjectView:
    requirements = [
        RequirementView(
            concept=requirement.concept.title,
            skill=requirement.concept.skill.title,
            required=requirement.minimum_mastery,
            current=mastery.get(requirement.concept_id, 0),
        )
        for requirement in project.requirements.all()
    ]
    completion = completions.get(project.pk)
    started = project.pk in started_ids
    met = all(requirement.met for requirement in requirements)
    if completion is not None:
        state = COMPLETED
    elif started:
        # Work already begun stays reachable even if mastery later dips.
        state = IN_PROGRESS
    elif met:
        state = AVAILABLE
    else:
        state = LOCKED
    stages = _stage_views(list(project.published_stages), done_ids)
    if state == LOCKED:
        for stage in stages:
            stage.available = stage.current = False
    return ProjectView(project, state, requirements, stages, completion, started)


def _prefetched(queryset):
    return queryset.prefetch_related(
        Prefetch(
            "requirements",
            queryset=ProjectConceptRequirement.objects.select_related("concept__skill"),
        ),
        Prefetch(
            "stages",
            queryset=ProjectStage.objects.filter(is_published=True).order_by("order", "id"),
            to_attr="published_stages",
        ),
    ).select_related("world")


def _learner_facts(enrollment: Enrollment, project_ids):
    done_ids = set(
        ProjectSubmission.objects.filter(
            enrollment=enrollment,
            project_id__in=project_ids,
            status=AttemptStatus.CORRECT,
            is_correct=True,
        ).values_list("stage_id", flat=True)
    )
    started_ids = set(
        ProjectSubmission.objects.filter(
            enrollment=enrollment, project_id__in=project_ids
        ).values_list("project_id", flat=True)
    ) | set(
        ProjectDraft.objects.filter(enrollment=enrollment, project_id__in=project_ids).values_list(
            "project_id", flat=True
        )
    )
    completions = {
        completion.project_id: completion
        for completion in ProjectCompletion.objects.filter(
            enrollment=enrollment, project_id__in=project_ids
        )
    }
    return done_ids, started_ids, completions


def project_overview(enrollment: Enrollment) -> list[ProjectView]:
    """Every published project of the enrollment's World with this learner's state."""
    projects = list(_prefetched(published_projects(enrollment.world_id)))
    ids = [project.pk for project in projects]
    done_ids, started_ids, completions = _learner_facts(enrollment, ids)
    mastery = _mastery_map(enrollment)
    return [
        _build(project, enrollment, mastery, done_ids, started_ids, completions)
        for project in projects
    ]


def project_view(enrollment: Enrollment, project: Project) -> ProjectView:
    project = _prefetched(Project.objects.filter(pk=project.pk)).get()
    done_ids, started_ids, completions = _learner_facts(enrollment, [project.pk])
    return _build(project, enrollment, _mastery_map(enrollment), done_ids, started_ids, completions)


def stage_view(view: ProjectView, stage: ProjectStage) -> StageView | None:
    return next((item for item in view.stages if item.stage.pk == stage.pk), None)


def latest_correct_source(enrollment: Enrollment, stage: ProjectStage) -> str | None:
    submission = (
        ProjectSubmission.objects.filter(
            enrollment=enrollment, stage=stage, status=AttemptStatus.CORRECT, is_correct=True
        )
        .order_by("-submitted_at", "-id")
        .first()
    )
    return submission.submitted_source if submission else None


def latest_submission(enrollment: Enrollment, stage: ProjectStage) -> ProjectSubmission | None:
    return (
        ProjectSubmission.objects.filter(enrollment=enrollment, stage=stage)
        .order_by("-submitted_at", "-id")
        .first()
    )


def reset_source(enrollment: Enrollment, view: ProjectView, stage: ProjectStage) -> str:
    """Stage 1: the project's starter code. Later: the last passing code of the stage before."""
    item = stage_view(view, stage)
    if item is None or item.number == 1:
        first = view.stages[0].stage if view.stages else stage
        return first.starter_code
    previous = view.stages[item.number - 2].stage
    return latest_correct_source(enrollment, previous) or stage.starter_code


def workspace_source(enrollment: Enrollment, view: ProjectView, stage: ProjectStage) -> str:
    draft = ProjectDraft.objects.filter(enrollment=enrollment, project=view.project).first()
    if draft is not None and draft.source_code.strip():
        return draft.source_code
    return reset_source(enrollment, view, stage) or stage.starter_code


def completed_projects(learner) -> list[ProjectCompletion]:
    return list(
        ProjectCompletion.objects.filter(enrollment__learner=learner)
        .select_related("project", "enrollment__world")
        .order_by("completed_at", "id")
    )


def stage_titles_done(view: ProjectView) -> list[str]:
    return [item.stage.title for item in view.stages if item.done]
