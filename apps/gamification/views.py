from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from apps.attempts.models import ExerciseAttempt
from apps.attempts.views import json_error, json_login_required
from apps.gamification.selectors import attempt_rewards, header_stats
from apps.learners.services import get_or_create_learner_profile


@require_GET
@json_login_required
def summary(request: HttpRequest) -> JsonResponse:
    """The signed-in learner's XP, level and streak, plus what one of their attempts earned."""
    learner = get_or_create_learner_profile(request.user)
    stats = header_stats(learner)
    body = {
        "xp": stats["xp"],
        "xp_display": stats["xp_display"],
        "level": stats["level"],
        "level_percent": stats["level_percent"],
        "streak_days": stats["streak_days"],
    }
    if "attempt" in request.GET:
        try:
            attempt_id = int(request.GET["attempt"])
        except ValueError:
            return json_error("not_found", 404)
        attempt = ExerciseAttempt.objects.filter(pk=attempt_id, enrollment__learner=learner).first()
        if attempt is None:
            return json_error("not_found", 404)
        body["rewards"] = attempt_rewards(attempt)
    return JsonResponse(body)
