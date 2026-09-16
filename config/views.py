from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

# Static demo content for the Phase 1 product shell. Presentation only: nothing here is
# persisted or calculated. Real progress, curriculum and tutor data arrive in later phases.
DEMO_PROGRESS = {
    "level": 14,
    "xp": "7,840",
    "streak_days": 12,
    "mastery": 31,
    "current_skill": "Loops",
}

DEMO_SKILLS = [
    {"name": "Variables", "status": "Mastered", "state": "mastered"},
    {"name": "Conditions", "status": "Mastered", "state": "mastered"},
    {"name": "Lists", "status": "Practising", "state": "practising"},
    {"name": "Loops", "status": "Learning", "state": "learning", "current": True},
    {"name": "Functions", "status": "Locked", "state": "locked"},
    {"name": "Dictionaries", "status": "Locked", "state": "locked", "extra": True},
    {"name": "File I/O", "status": "Locked", "state": "locked", "extra": True},
    {"name": "Error Handling", "status": "Locked", "state": "locked", "extra": True},
    {"name": "OOP", "status": "Locked", "state": "locked"},
]

DEMO_LESSON = {
    "course": "Python Basics",
    "title": "Loops",
    "description": "Use loops to repeat actions and work with data more efficiently.",
    "number": 4,
    "total": 8,
    "exercise_number": 1,
    "exercise_title": "Print only numbers greater than 10",
    "instruction": (
        "Given a list of numbers, use a for loop to print only the numbers "
        "that are greater than 10."
    ),
    "output_lines": ["12", "15", "20"],
    "tutor_hint": "Look again at the loop condition.",
    "tutor_messages": [
        "You're on the right track! Make sure you're checking if each number is greater "
        "than 10 inside the loop. The condition goes inside the if statement.",
        "The loop goes through each item in the list one by one. Compare each item "
        "with 10 before printing it.",
    ],
    "next_up": {
        "badge": "Boss Challenge",
        "title": "Build a Number Analyzer",
        "description": (
            "Create a program that analyzes a list of numbers and returns useful "
            "statistics (count, max, min, average) using loops."
        ),
    },
}

DEMO_QUOTE = "Small steps build extraordinary results."


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    context = {
        "progress": DEMO_PROGRESS,
        "skills": DEMO_SKILLS,
        "lesson": DEMO_LESSON,
        "quote": DEMO_QUOTE,
    }
    return render(request, "home.html", context)


@never_cache
@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: the process is up and serving requests. Does not query the database."""
    return JsonResponse({"status": "ok"})
