"""Builds the course player's page data from real learner state.

An orchestration layer only: the exercise shown comes from Next Best Action (unless the learner
followed a link to a specific exercise), progress from Learner Intelligence, and help from the
AI tutor. Nothing here is stored.
"""

import re
from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from apps.ai_tutor.config import get_tutor_config
from apps.ai_tutor.selectors import recent_completed_turns
from apps.attempts.models import ExerciseAttempt
from apps.attempts.presentation import attempt_list_item
from apps.course_player import presentation as text
from apps.curriculum.models import Lesson, Skill
from apps.exercises.models import Exercise, ResponseType
from apps.exercises.presentation import exercise_presentation
from apps.exercises.selectors import published_exercises, published_exercises_for_lesson
from apps.gamification.bosses import boss_exercise_ids
from apps.gamification.selectors import header_stats
from apps.learner_intelligence.selectors import world_summary
from apps.learners.models import Enrollment
from apps.next_action.engine import concept_contexts, next_action_for_enrollment
from apps.next_action.presentation import decision_presentation

QUOTE = "Small steps build extraordinary results."
TUTOR_HISTORY_LIMIT = 12
SKILL_WINDOW = 5
GAP = re.compile(r"(?<!\w)__(?!\w)")


def player_url(world_id: int) -> str:
    return reverse("course_player:world", args=[world_id])


def exercise_in_world(world_id: int, exercise_id: object) -> Exercise | None:
    """A published exercise of this World, or None (never another World's exercise)."""
    try:
        pk = int(exercise_id)
    except (TypeError, ValueError):
        return None
    return (
        published_exercises()
        .filter(pk=pk, lesson__concept__skill__world_id=world_id)
        .select_related("lesson__concept__skill__world")
        .first()
    )


# --- progress -----------------------------------------------------------------------------


def skill_map(enrollment: Enrollment, current_skill_id: int | None) -> list[dict]:
    contexts = concept_contexts(enrollment)
    by_skill: dict[int, list] = {}
    for context in contexts:
        by_skill.setdefault(context.skill_id, []).append(context)
    skills = Skill.objects.filter(world_id=enrollment.world_id, is_published=True).order_by(
        "order", "id"
    )
    rows = []
    for skill in skills:
        concepts = by_skill.get(skill.pk, [])
        current = skill.pk == current_skill_id
        if concepts and all(c.band == "mastered" for c in concepts):
            state, status = "mastered", "Mastered"
        elif any(c.band in ("practising", "mastered") for c in concepts):
            state, status = "practising", "Practising"
        elif current or any(c.started for c in concepts):
            state, status = "learning", "Learning"
        elif not any(c.prerequisites_ready for c in concepts):
            state, status = "locked", "Locked"
        else:
            state, status = "available", "Ready"
        rows.append(
            {
                "id": skill.pk,
                "name": skill.title,
                "state": state,
                "status": status,
                "current": current,
                "extra": False,
            }
        )
    # On small screens the map is a short row: keep a window around the current skill.
    index = next((i for i, row in enumerate(rows) if row["current"]), 0)
    start = max(0, min(index - SKILL_WINDOW // 2, len(rows) - SKILL_WINDOW))
    for i, row in enumerate(rows):
        row["extra"] = not start <= i < start + SKILL_WINDOW
    return rows


def progress_context(enrollment: Enrollment, current_skill: Skill | None, now=None) -> dict:
    summary = world_summary(enrollment, now=now)
    # Platform-wide gamification (XP, level, streak) next to this course's own mastery.
    stats = header_stats(enrollment.learner, today=timezone.localdate(now) if now else None)
    return {
        "progress": {
            "level": stats["level"],
            "xp": stats["xp_display"],
            "streak_days": stats["streak_days"],
            "level_percent": stats["level_percent"],
            "course": enrollment.world.title,
            "mastery": round(summary["mastery"]),
            "current_skill": current_skill.title if current_skill else "—",
        },
        "skills": skill_map(enrollment, current_skill.pk if current_skill else None),
    }


# --- exercise ---------------------------------------------------------------------------


def _lines(value: str) -> list[str]:
    return value.split("\n") if value else []


def fill_gap_lines(template: str) -> list[list[dict]]:
    """Template lines as segments, with one ``{"gap": True}`` where the answer goes."""
    match = GAP.search(template or "")
    if match is None:
        return [[{"text": line}] for line in _lines(template)] or [[{"gap": True}]]
    before = template[: match.start()].split("\n")
    after = template[match.end() :].split("\n")
    lines = [[{"text": line}] for line in before[:-1]]
    lines.append([{"text": before[-1]}, {"gap": True}, {"text": after[0]}])
    lines.extend([{"text": line}] for line in after[1:])
    return lines


def exercise_view(exercise: Exercise, is_boss: bool = False) -> dict:
    public = exercise_presentation(exercise)
    content = public["content"] if isinstance(public["content"], dict) else {}
    kind = public["response_type"]
    view = {
        "id": public["id"],
        "title": public["title"],
        "prompt": public["prompt"],
        "instructions": public["instructions"],
        "response_type": kind,
        "learning_mode": public["learning_mode"],
        "kicker": text.BOSS_LABEL if is_boss else text.KICKERS.get(kind, "Exercise"),
        "is_boss": is_boss,
        "tab": text.EDITOR_TABS.get(kind, "Your answer"),
        "supported": kind in text.SUPPORTED_TYPES,
        "is_code": kind == ResponseType.CODE,
        "is_choice": kind == ResponseType.MULTIPLE_CHOICE,
        "is_gap": kind == ResponseType.FILL_GAP,
        "is_line": kind in text.LINE_TYPES,
        "is_text": kind in text.TEXT_TYPES,
        "starter_code": "",
        "snippet_lines": [],
        "options": [],
        "gap_lines": [],
        "unit": "",
        "source_text": "",
    }
    if kind == ResponseType.CODE:
        starter = content.get("starter_code")
        view["starter_code"] = starter if isinstance(starter, str) else ""
    elif kind == ResponseType.MULTIPLE_CHOICE:
        view["snippet_lines"] = _lines((content.get("code") or "").rstrip("\n"))
        view["options"] = [
            {"id": option["id"], "text": option["text"]}
            for option in content.get("options", [])
            if isinstance(option, dict) and "id" in option and "text" in option
        ]
    elif kind == ResponseType.FILL_GAP:
        view["gap_lines"] = fill_gap_lines(content.get("template", ""))
    elif kind in text.LINE_TYPES:
        view["unit"] = content.get("unit", "") if isinstance(content.get("unit"), str) else ""
    elif kind == ResponseType.TRANSLATION:
        source = content.get("source_text")
        view["source_text"] = source if isinstance(source, str) else ""
    return view


def lesson_position(lesson: Lesson) -> tuple[int, int]:
    """(position, total) among the published lessons of the lesson's Skill, authored order."""
    ids = list(
        Lesson.objects.filter(
            is_published=True,
            concept__is_published=True,
            concept__skill_id=lesson.concept.skill_id,
        )
        .order_by("concept__order", "concept_id", "order", "id")
        .values_list("id", flat=True)
    )
    position = ids.index(lesson.pk) + 1 if lesson.pk in ids else 1
    return position, max(len(ids), 1)


def latest_attempt(enrollment: Enrollment, exercise: Exercise) -> dict | None:
    attempt = (
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise)
        .prefetch_related("mistakes")
        .order_by("-submitted_at", "-id")
        .first()
    )
    return attempt_list_item(attempt) if attempt else None


# --- page ---------------------------------------------------------------------------------


def build_course_player_context(
    enrollment: Enrollment, *, exercise: Exercise | None = None, now: datetime | None = None
) -> dict:
    now = now or timezone.now()
    world = enrollment.world
    url = player_url(world.pk)
    decision = decision_presentation(next_action_for_enrollment(enrollment, now=now), enrollment)
    bosses = boss_exercise_ids(world.pk)
    next_up = text.next_up_view(decision, url, bosses)

    if exercise is None and decision["exercise"]:
        exercise = exercise_in_world(world.pk, decision["exercise"]["id"])

    tutor_available = get_tutor_config().available
    turns = recent_completed_turns(enrollment, TUTOR_HISTORY_LIMIT)
    history = []
    for index, turn in enumerate(turns):
        older = index < len(turns) - 1
        if turn.user_message:
            history.append({"role": "learner", "text": turn.user_message, "older": older})
        history.append({"role": "tutor", "text": turn.assistant_message, "older": older})

    if exercise is None:
        state = "course_complete" if decision["action"] == "course_complete" else "no_action"
        current_skill = None
        lesson = {
            "course": world.title,
            "title": next_up["title"],
            "description": next_up["description"],
            "number": 0,
            "total": 0,
            "exercise_title": next_up["title"],
            "instruction": next_up["description"],
            "next_up": next_up,
        }
        view = None
        latest = None
    else:
        state = "exercise"
        lesson_obj = exercise.lesson
        concept = lesson_obj.concept
        current_skill = concept.skill
        number, total = lesson_position(lesson_obj)
        exercise_ids = list(published_exercises_for_lesson(lesson_obj).values_list("id", flat=True))
        view = exercise_view(exercise, is_boss=exercise.pk in bosses)
        latest = latest_attempt(enrollment, exercise)
        lesson = {
            "course": world.title,
            "title": lesson_obj.title,
            "description": lesson_obj.objective or concept.learning_objective,
            "number": number,
            "total": total,
            "exercise_number": (
                exercise_ids.index(exercise.pk) + 1 if exercise.pk in exercise_ids else 1
            ),
            "exercise_title": view["title"],
            "instruction": view["prompt"],
            "extra_instruction": view["instructions"],
            "next_up": next_up,
        }

    if latest:
        output_lines = text.feedback_lines(latest)
    elif view:
        output_lines = [text.IDLE_OUTPUT.get(view["response_type"], text.DEFAULT_IDLE_OUTPUT)]
    else:
        output_lines = []

    progress = progress_context(enrollment, current_skill, now=now)
    config = {
        "worldId": world.pk,
        "state": state,
        "exercise": (
            {
                "id": view["id"],
                "responseType": view["response_type"],
                "starterCode": view["starter_code"],
            }
            if view
            else None
        ),
        "urls": {
            "player": url,
            "progress": reverse("course_player:progress", args=[world.pk]),
            "attempts": (reverse("attempts:exercise_attempts", args=[view["id"]]) if view else ""),
            "nextAction": reverse("next_action:next_action", args=[world.pk]),
            "tutor": reverse("ai_tutor:turns", args=[world.pk]),
            "gamification": reverse("gamification:summary"),
        },
        "bossExerciseIds": bosses,
        "tutorAvailable": tutor_available,
        "text": {
            "actionLabels": text.ACTION_LABELS,
            "actionButtons": text.ACTION_BUTTONS,
            "reasons": text.REASON_TEXT,
            "statuses": text.STATUS_LABELS,
            "tutorUnavailable": text.TUTOR_UNAVAILABLE,
            "bossBadge": text.BOSS_LABEL,
        },
    }
    return {
        **progress,
        "lesson": lesson,
        "course": {"title": world.title, "domain": world.domain},
        "quote": QUOTE,
        "player": {
            "world_id": world.pk,
            "state": state,
            "exercise": view,
            "output_lines": output_lines,
            "has_error": bool(latest and (latest.get("diagnostics") or {}).get("error_type")),
            "tutor_available": tutor_available,
            "tutor_history": history,
            "tutor_intro": text.TUTOR_INTRO,
            "tutor_unavailable": text.TUTOR_UNAVAILABLE,
            "config": config,
        },
    }
