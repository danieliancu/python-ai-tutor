"""Project pages (server-rendered) and their small JSON endpoints."""

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.ai_tutor.config import get_tutor_config
from apps.ai_tutor.services import TutorRequestError
from apps.attempts.views import json_error, json_login_required
from apps.course_player.services import player_url, progress_context
from apps.gamification.selectors import header_stats, submission_rewards
from apps.projects import coach, presentation, selectors
from apps.projects.access import get_project, get_stage, project_enrollment
from apps.projects.services import ProjectRequestError, save_draft, submit_stage

COACH_HISTORY_SHOWN = 12
TUTOR_INTRO = (
    "I'm your project coach. Ask about your code, or type /hint, /explain, /solution or /next. "
    "I'll help you build it — I won't write it for you."
)
TUTOR_UNAVAILABLE = "AI Tutor is currently unavailable."
ERROR_MESSAGES = {
    "tutor_unavailable": "The tutor is temporarily unavailable.",
    "tutor_turn_in_progress": "A tutor reply for this project is already being written.",
}


def _base_context(request: HttpRequest, enrollment, page_label: str, has_tutor=False) -> dict:
    world = enrollment.world
    context = progress_context(enrollment, None)
    context.update(
        {
            "course": {"title": world.title, "domain": world.domain},
            "world": world,
            "nav": {
                "page": "projects",
                "learn_url": player_url(world.pk),
                "projects_url": reverse("projects:list", args=[world.pk]),
                "main_label": page_label,
                "has_tutor": has_tutor,
            },
            "account_name": enrollment.learner.preferred_name or request.user.get_username(),
        }
    )
    return context


@login_required
@require_GET
def project_list(request: HttpRequest, world_id: int) -> HttpResponse:
    enrollment = project_enrollment(request.user, world_id)
    context = _base_context(request, enrollment, "Projects")
    context["projects"] = selectors.project_overview(enrollment)
    return render(request, "projects/list.html", context)


@login_required
@require_GET
def project_detail(request: HttpRequest, world_id: int, project_slug: str) -> HttpResponse:
    enrollment = project_enrollment(request.user, world_id)
    project = get_project(enrollment, project_slug)
    context = _base_context(request, enrollment, project.title)
    context["view"] = selectors.project_view(enrollment, project)
    context["stage_labels"] = presentation.STAGE_LABELS
    context["stage_dots"] = presentation.STAGE_DOTS
    return render(request, "projects/detail.html", context)


def _stage_urls(world_id, project, stage) -> dict:
    args = [world_id, project.slug]
    return {
        "draft": reverse("projects:draft", args=args),
        "submit": reverse("projects:submit", args=[*args, stage.slug]),
        "coach": reverse("projects:coach", args=[*args, stage.slug]),
        "detail": reverse("projects:detail", args=args),
        "summary": reverse("gamification:summary"),
    }


@login_required
@require_GET
def project_stage(
    request: HttpRequest, world_id: int, project_slug: str, stage_slug: str
) -> HttpResponse:
    enrollment = project_enrollment(request.user, world_id)
    project = get_project(enrollment, project_slug)
    stage = get_stage(project, stage_slug)
    view = selectors.project_view(enrollment, project)
    item = selectors.stage_view(view, stage)
    if not view.unlocked or item is None or not item.available:
        return redirect("projects:detail", world_id=world_id, project_slug=project.slug)

    next_item = view.stages[item.number] if item.number < view.total else None
    tutor_available = get_tutor_config().available
    turns = coach.project_turns(enrollment, project, COACH_HISTORY_SHOWN)
    history = []
    for index, turn in enumerate(turns):
        older = index < len(turns) - 1
        if turn.user_message:
            history.append({"role": "learner", "text": turn.user_message, "older": older})
        history.append({"role": "tutor", "text": turn.assistant_message, "older": older})

    urls = _stage_urls(world_id, project, stage)
    next_url = (
        reverse("projects:stage", args=[world_id, project.slug, next_item.stage.slug])
        if next_item
        else ""
    )
    context = _base_context(request, enrollment, stage.title, has_tutor=True)
    context.update(
        {
            "view": view,
            "item": item,
            "stage": stage,
            "source": selectors.workspace_source(enrollment, view, stage),
            "output_lines": presentation.submission_lines(
                selectors.latest_submission(enrollment, stage)
            ),
            "next_url": next_url,
            "stage_labels": presentation.STAGE_LABELS,
            "stage_dots": presentation.STAGE_DOTS,
            "tutor_available": tutor_available,
            "tutor_history": history,
            "tutor_intro": TUTOR_INTRO,
            "tutor_unavailable": TUTOR_UNAVAILABLE,
            "config": {
                "stage": stage.slug,
                "stageDone": item.done,
                "nextUrl": next_url,
                "resetSource": selectors.reset_source(enrollment, view, stage),
                "urls": {**urls, "tutor": urls["coach"]},
                "tutorAvailable": tutor_available,
                "text": {
                    "statuses": presentation.STATUS_LABELS,
                    "tutorUnavailable": TUTOR_UNAVAILABLE,
                },
            },
        }
    )
    return render(request, "projects/stage.html", context)


def _json_body(request: HttpRequest, allowed: set[str]) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise ProjectRequestError("malformed_json", 400) from None
    if not isinstance(body, dict):
        raise ProjectRequestError("body_must_be_an_object", 400)
    if set(body) - allowed:
        raise ProjectRequestError("unknown_fields", 400)
    return body


def _json_view(handler):
    """Shared access checks and error mapping for the project JSON endpoints."""

    @json_login_required
    @require_POST
    def view(request: HttpRequest, world_id: int, project_slug: str, **kwargs):
        try:
            enrollment = project_enrollment(request.user, world_id)
            project = get_project(enrollment, project_slug)
            return handler(request, enrollment, project, **kwargs)
        except PermissionDenied:
            return json_error("forbidden", 403)
        except Http404:
            return json_error("not_found", 404)
        except ProjectRequestError as exc:
            return json_error(exc.code, exc.status)

    view.__name__ = handler.__name__
    return view


@_json_view
def draft(request, enrollment, project):
    body = _json_body(request, {"stage", "source"})
    stage_slug = body.get("stage")
    if not isinstance(stage_slug, str):
        raise ProjectRequestError("stage_required", 400)
    stage = get_stage(project, stage_slug)
    saved = save_draft(enrollment, project, stage, body.get("source"))
    return JsonResponse({"saved_at": saved.updated_at.isoformat()})


@_json_view
def submit(request, enrollment, project, stage_slug):
    body = _json_body(request, {"source", "duration_seconds"})
    stage = get_stage(project, stage_slug)
    outcome = submit_stage(
        enrollment, project, stage, body.get("source"), body.get("duration_seconds")
    )
    world_id = enrollment.world_id
    payload = presentation.submission_payload(outcome.submission)
    stats = header_stats(enrollment.learner)
    payload.update(
        {
            "stage_completed": outcome.stage_completed,
            "project_completed": outcome.project_completed,
            "next_stage_url": (
                reverse("projects:stage", args=[world_id, project.slug, outcome.next_stage.slug])
                if outcome.next_stage
                else ""
            ),
            "project_url": reverse("projects:detail", args=[world_id, project.slug]),
            "rewards": submission_rewards(outcome.submission),
            "stats": {
                "xp_display": stats["xp_display"],
                "level": stats["level"],
                "level_percent": stats["level_percent"],
                "streak_days": stats["streak_days"],
            },
        }
    )
    return JsonResponse(payload, status=201)


@_json_view
def coach_turn(request, enrollment, project, stage_slug):
    body = _json_body(request, {"intent", "message", "source"})
    stage = get_stage(project, stage_slug)
    try:
        turn = coach.request_project_turn(
            enrollment,
            project,
            stage,
            intent=body.get("intent", "ask"),
            message=body.get("message", ""),
            source=body.get("source"),
        )
    except TutorRequestError as exc:
        extra = {"message": ERROR_MESSAGES[exc.code]} if exc.code in ERROR_MESSAGES else {}
        return json_error(exc.code, exc.status, **extra)
    return JsonResponse(coach.coach_presentation(turn), status=201)
