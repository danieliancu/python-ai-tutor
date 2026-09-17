"""Gamification rules. Every award is derived from stored learning data and is idempotent.

The same functions serve the live post-attempt step and ``rebuild_gamification``: each rule
looks at attempt history (and learner intelligence for skill mastery), and database
uniqueness guarantees an award happens at most once, whatever retries or races occur.
"""

import logging
from collections import Counter

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.curriculum.models import Concept
from apps.exercises.models import Exercise
from apps.gamification import achievements as codes
from apps.gamification.models import (
    Achievement,
    AchievementAward,
    BossChallenge,
    BossCompletion,
    GamificationProfile,
    XPEvent,
    XPEventType,
)
from apps.gamification.streaks import QUALIFYING_STATUSES, streak_from_days
from apps.learner_intelligence.models import ConceptState, MasteryBand
from apps.learners.models import Enrollment, LearnerProfile
from apps.projects.models import ProjectCompletion, ProjectSubmission

logger = logging.getLogger(__name__)

EXERCISE_XP = 20
FIRST_TRY_XP = 5
INDEPENDENCE_XP = 5
SKILL_MASTERY_XP = 50
TEN_DOWN_COUNT = 10
ON_A_ROLL_DAYS = 3
CONSISTENT_DAYS = 7
# A checked project stage counts as learning; unchecked submissions don't.
PROJECT_QUALIFYING_STATUSES = (AttemptStatus.CORRECT, AttemptStatus.INCORRECT)


# --- XP -------------------------------------------------------------------------------------


def _award_xp(
    enrollment, event_type, xp, source_key, attempt=None, project_submission=None, **metadata
) -> bool:
    """Record an XP event once. Returns whether this call created it."""
    try:
        with transaction.atomic():
            _, created = XPEvent.objects.get_or_create(
                learner_id=enrollment.learner_id,
                source_key=source_key,
                defaults={
                    "world_id": enrollment.world_id,
                    "enrollment": enrollment,
                    "attempt": attempt,
                    "project_submission": project_submission,
                    "event_type": event_type,
                    "xp": xp,
                    "metadata": metadata,
                },
            )
    except IntegrityError:
        # A concurrent submission recorded it first.
        return False
    return created


def _is_correct(attempt: ExerciseAttempt) -> bool:
    return attempt.status == AttemptStatus.CORRECT and attempt.is_correct is True


def sync_enrollment_exercise(enrollment: Enrollment, exercise: Exercise) -> int:
    """Exercise completion, first-try, independence and boss rewards. Returns awards created."""
    attempts = list(
        ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise).order_by(
            "attempt_number", "id"
        )
    )
    first_correct = next((a for a in attempts if _is_correct(a)), None)
    if first_correct is None:
        return 0

    key = f"exercise:{exercise.pk}"
    created = _award_xp(
        enrollment,
        XPEventType.EXERCISE_COMPLETED,
        EXERCISE_XP,
        f"{key}:completed",
        first_correct,
        exercise_id=exercise.pk,
    )
    if attempts[0].pk == first_correct.pk and first_correct.attempt_number == 1:
        created += _award_xp(
            enrollment,
            XPEventType.FIRST_TRY,
            FIRST_TRY_XP,
            f"{key}:first_try",
            first_correct,
            exercise_id=exercise.pk,
        )
    if (
        first_correct.hint_level == 0
        and not first_correct.used_explanation
        and not first_correct.used_solution
    ):
        created += _award_xp(
            enrollment,
            XPEventType.INDEPENDENCE,
            INDEPENDENCE_XP,
            f"{key}:independence",
            first_correct,
            exercise_id=exercise.pk,
        )

    boss = BossChallenge.objects.filter(exercise=exercise, is_active=True).first()
    if boss is not None:
        try:
            with transaction.atomic():
                BossCompletion.objects.get_or_create(
                    enrollment=enrollment, boss=boss, defaults={"attempt": first_correct}
                )
        except IntegrityError:
            pass
        created += _award_xp(
            enrollment,
            XPEventType.BOSS_COMPLETED,
            boss.bonus_xp,
            f"boss:{boss.pk}:completed",
            first_correct,
            exercise_id=exercise.pk,
            boss_id=boss.pk,
        )
    return created


def sync_skill_mastery(enrollment: Enrollment, skill_id: int, attempt=None) -> int:
    """+50 XP the first time every published concept of a skill is in the mastered band."""
    concept_ids = set(
        Concept.objects.filter(
            skill_id=skill_id, is_published=True, skill__is_published=True
        ).values_list("id", flat=True)
    )
    if not concept_ids:
        return 0
    mastered = ConceptState.objects.filter(
        enrollment=enrollment, concept_id__in=concept_ids, mastery_band=MasteryBand.MASTERED
    ).count()
    if mastered != len(concept_ids):
        return 0
    return int(
        _award_xp(
            enrollment,
            XPEventType.SKILL_MASTERED,
            SKILL_MASTERY_XP,
            f"skill:{skill_id}:mastered",
            attempt,
            skill_id=skill_id,
        )
    )


# --- learner summary ------------------------------------------------------------------------


def _days(queryset) -> set:
    return set(
        queryset.annotate(day=TruncDate("submitted_at", tzinfo=timezone.get_current_timezone()))
        .values_list("day", flat=True)
        .distinct()
    )


def activity_days(learner: LearnerProfile) -> set:
    """Calendar days (Django's time zone) with judged exercise or project work, in any course."""
    return _days(
        ExerciseAttempt.objects.filter(enrollment__learner=learner, status__in=QUALIFYING_STATUSES)
    ) | _days(
        ProjectSubmission.objects.filter(
            enrollment__learner=learner, status__in=PROJECT_QUALIFYING_STATUSES
        )
    )


def sync_learner(
    learner: LearnerProfile,
    attempt: ExerciseAttempt | None = None,
    project_submission: ProjectSubmission | None = None,
) -> list:
    """Recompute the materialised profile from events and attempts, then achievements.

    Returns the achievement awards created by this call.
    """
    with transaction.atomic():
        GamificationProfile.objects.get_or_create(learner=learner)
        profile = GamificationProfile.objects.select_for_update().get(learner=learner)
        total = XPEvent.objects.filter(learner=learner).aggregate(total=Sum("xp"))["total"]
        current, longest, last_day = streak_from_days(activity_days(learner))
        profile.total_xp = total or 0
        profile.current_streak = current
        profile.longest_streak = longest
        profile.last_activity_date = last_day
        profile.save()
    return _sync_achievements(learner, profile, attempt, project_submission)


def _sync_achievements(learner, profile, attempt, project_submission=None) -> list:
    events = XPEvent.objects.filter(learner=learner)
    counts = Counter(events.values_list("event_type", flat=True))
    first_boss = (
        BossCompletion.objects.filter(enrollment__learner=learner)
        .select_related("enrollment")
        .first()
    )
    earned = {
        codes.FIRST_STEP: counts[XPEventType.EXERCISE_COMPLETED] >= 1,
        codes.INDEPENDENT_THINKER: counts[XPEventType.INDEPENDENCE] >= 1,
        codes.ON_A_ROLL: profile.longest_streak >= ON_A_ROLL_DAYS,
        codes.CONSISTENT_LEARNER: profile.longest_streak >= CONSISTENT_DAYS,
        codes.SKILL_MASTERED: counts[XPEventType.SKILL_MASTERED] >= 1,
        codes.BOSS_CLEARED: first_boss is not None,
        codes.TEN_DOWN: counts[XPEventType.EXERCISE_COMPLETED] >= TEN_DOWN_COUNT,
        codes.PROJECT_BUILDER: counts[XPEventType.PROJECT_COMPLETED] >= 1,
    }
    source_type = {
        codes.FIRST_STEP: XPEventType.EXERCISE_COMPLETED,
        codes.INDEPENDENT_THINKER: XPEventType.INDEPENDENCE,
        codes.SKILL_MASTERED: XPEventType.SKILL_MASTERED,
        codes.BOSS_CLEARED: XPEventType.BOSS_COMPLETED,
        codes.TEN_DOWN: XPEventType.EXERCISE_COMPLETED,
        codes.PROJECT_BUILDER: XPEventType.PROJECT_COMPLETED,
    }
    owned = set(
        AchievementAward.objects.filter(learner=learner).values_list("achievement__code", flat=True)
    )
    pending = [code for code, ok in earned.items() if ok and code not in owned]
    if not pending:
        return []

    created = []
    for achievement in Achievement.objects.filter(code__in=pending, is_active=True):
        trigger = attempt or project_submission
        if trigger is not None:
            context = {
                "enrollment_id": trigger.enrollment_id,
                "world_id": trigger.enrollment.world_id,
                "attempt": attempt,
                "project_submission": project_submission,
            }
        else:
            # Rebuilds attribute the award to the course where it was first earned.
            event = (
                events.filter(event_type=source_type.get(achievement.code))
                .order_by("created_at", "id")
                .first()
                if achievement.code in source_type
                else events.order_by("created_at", "id").first()
            )
            context = {
                "enrollment_id": event.enrollment_id if event else None,
                "world_id": event.world_id if event else None,
            }
        try:
            with transaction.atomic():
                award, was_created = AchievementAward.objects.get_or_create(
                    learner=learner, achievement=achievement, defaults=context
                )
        except IntegrityError:
            continue
        if was_created:
            created.append(award)
    return created


# --- entry points ---------------------------------------------------------------------------


def refresh_for_attempt(attempt: ExerciseAttempt) -> list:
    """The post-attempt step: runs after learner intelligence and misconceptions."""
    enrollment = attempt.enrollment
    sync_enrollment_exercise(enrollment, attempt.exercise)
    sync_skill_mastery(enrollment, attempt.exercise.lesson.concept.skill_id, attempt)
    return sync_learner(enrollment.learner, attempt)


def sync_project_completion(completion: ProjectCompletion) -> int:
    """The project's XP reward, once per learner and project."""
    project = completion.project
    return int(
        _award_xp(
            completion.enrollment,
            XPEventType.PROJECT_COMPLETED,
            project.xp_reward,
            f"project:{project.pk}:completed",
            project_submission=completion.final_submission,
            project_id=project.pk,
        )
    )


def refresh_for_project_submission(submission: ProjectSubmission) -> list:
    """The post-submission step for projects: completion reward, streak and achievements."""
    completion = (
        ProjectCompletion.objects.filter(
            enrollment_id=submission.enrollment_id, project_id=submission.project_id
        )
        .select_related("project", "enrollment", "final_submission")
        .first()
    )
    if completion is not None:
        sync_project_completion(completion)
    return sync_learner(submission.enrollment.learner, project_submission=submission)


def ensure_achievements() -> int:
    """Create any catalogue achievement that is missing (admin edits are kept)."""
    created = 0
    for definition in codes.ACHIEVEMENTS:
        _, was_created = Achievement.objects.get_or_create(
            code=definition["code"],
            defaults={key: value for key, value in definition.items() if key != "code"},
        )
        created += was_created
    return created


def rebuild_gamification(learner_id: int | None = None, enrollment_id: int | None = None) -> dict:
    """Reconstruct XP, streaks, boss completions and achievements from stored history.

    Safe to run repeatedly: existing awards are kept and never duplicated.
    """
    ensure_achievements()
    enrollments = Enrollment.objects.select_related("learner").order_by("id")
    learners = LearnerProfile.objects.order_by("id")
    if learner_id is not None:
        enrollments = enrollments.filter(learner_id=learner_id)
        learners = learners.filter(pk=learner_id)
    if enrollment_id is not None:
        enrollments = enrollments.filter(pk=enrollment_id)
        learners = learners.filter(enrollments__pk=enrollment_id)

    xp_before = XPEvent.objects.count()
    awards_before = AchievementAward.objects.count()
    for enrollment in enrollments:
        exercise_ids = (
            ExerciseAttempt.objects.filter(
                enrollment=enrollment, status=AttemptStatus.CORRECT, is_correct=True
            )
            .values_list("exercise_id", flat=True)
            .distinct()
        )
        for exercise in Exercise.objects.filter(pk__in=list(exercise_ids)).order_by("id"):
            sync_enrollment_exercise(enrollment, exercise)
        skill_ids = (
            ConceptState.objects.filter(enrollment=enrollment, mastery_band=MasteryBand.MASTERED)
            .values_list("concept__skill_id", flat=True)
            .distinct()
        )
        for skill_id in sorted(set(skill_ids)):
            sync_skill_mastery(enrollment, skill_id)
        for completion in ProjectCompletion.objects.filter(enrollment=enrollment).select_related(
            "project", "enrollment", "final_submission"
        ):
            sync_project_completion(completion)

    learner_count = 0
    for learner in learners.distinct():
        sync_learner(learner)
        learner_count += 1
    return {
        "learners": learner_count,
        "xp_events_created": XPEvent.objects.count() - xp_before,
        "awards_created": AchievementAward.objects.count() - awards_before,
    }
