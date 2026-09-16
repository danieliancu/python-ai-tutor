from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

# Static demo content for the Phase 1 product shell. Presentation only: nothing here is
# persisted or calculated. Real progress and curriculum data arrive in later phases.
DEMO_PROGRESS = {
    "level": 14,
    "mastery": 31,
    "xp": "7,840",
    "streak_days": 12,
    "current_skill": "Loops",
}

DEMO_SKILLS = [
    {"name": "Variables", "status": "Mastered", "state": "mastered", "icon": "✓"},
    {"name": "Conditions", "status": "Mastered", "state": "mastered", "icon": "✓"},
    {"name": "Lists", "status": "Practising", "state": "practising", "icon": "◐"},
    {"name": "Loops", "status": "Learning", "state": "learning", "icon": "●", "current": True},
    {"name": "Functions", "status": "Locked", "state": "locked", "icon": "○"},
]

DEMO_LESSON = {
    "skill": "Loops",
    "step": 3,
    "total_steps": 5,
    "title": "Print only numbers greater than 10",
    "instruction": (
        "Loop through the list and print each number, but only when it is greater than 10."
    ),
    "code_lines": [
        "numbers = [4, 18, 7, 25, 10, 13]",
        "",
        "for number in numbers:",
        "    if number < 10:",
        "        print(number)",
    ],
    "highlight_line": 4,
    "tutor_hint": "Look again at the loop condition.",
    "tutor_detail": "Which numbers should reach print()? Compare that with what the if allows.",
}


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    lesson_percent = round(DEMO_LESSON["step"] / DEMO_LESSON["total_steps"] * 100)
    context = {
        "progress": DEMO_PROGRESS,
        "skills": DEMO_SKILLS,
        "lesson": DEMO_LESSON,
        "lesson_percent": lesson_percent,
    }
    return render(request, "home.html", context)


@never_cache
@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: the process is up and serving requests. Does not query the database."""
    return JsonResponse({"status": "ok"})
