from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.exercises.access import ACCESS_STATUSES
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile

# Static demo content for the public (signed-out) product shell. Presentation only: nothing
# here is persisted or calculated. Signed-in learners get the real course player instead.
DEMO_PROGRESS = {
    "level": 14,
    "xp": "7,840",
    "streak_days": 12,
    "mastery": 31,
    "current_skill": "Loops",
    "course": "Python Foundations",
    "level_percent": 70,
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
    "course": "Python Foundations",
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
    if request.user.is_authenticated:
        return _learner_home(request)
    context = {
        "progress": DEMO_PROGRESS,
        "skills": DEMO_SKILLS,
        "lesson": DEMO_LESSON,
        "quote": DEMO_QUOTE,
        "account_name": _account_name(request),
    }
    return render(request, "home.html", context)


def _learner_home(request: HttpRequest) -> HttpResponse:
    """Signed-in learners go to their course (first active enrollment, else first completed)."""
    enrollments = Enrollment.objects.filter(
        learner__user=request.user, status__in=ACCESS_STATUSES, world__is_published=True
    )
    enrollment = (
        enrollments.filter(status=EnrollmentStatus.ACTIVE).order_by("enrolled_at", "id").first()
        or enrollments.order_by("enrolled_at", "id").first()
    )
    if enrollment is not None:
        return redirect("course_player:world", world_id=enrollment.world_id)
    profile = LearnerProfile.objects.filter(user=request.user).first()
    if profile is None or not profile.has_completed_onboarding:
        return redirect("learners:onboarding")
    return redirect("learners:profile")


def _account_name(request: HttpRequest) -> str:
    """How the top bar greets a signed-in user. Reads the profile without creating one."""
    if not request.user.is_authenticated:
        return ""
    preferred = (
        LearnerProfile.objects.filter(user=request.user)
        .values_list("preferred_name", flat=True)
        .first()
    )
    return preferred or request.user.get_username()


@never_cache
@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: the process is up and serving requests. Does not query the database."""
    return JsonResponse({"status": "ok"})
