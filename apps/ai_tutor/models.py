"""Tutor conversation and per-exercise assistance state.

These rows are interaction history, not learner intelligence: they never change mastery,
misconceptions or progression. Prompts, provider payloads and exercise answers are never stored.
"""

from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.ai_tutor.constants import MAX_HINT_LEVEL, Intent, ResponseKind, TurnStatus
from apps.attempts.models import ExerciseAttempt
from apps.exercises.models import Exercise
from apps.learners.models import Enrollment


class TutorTurn(models.Model):
    """One learner message and the tutor's reply (or the safe reason there was none)."""

    Intent = Intent
    Kind = ResponseKind
    Status = TurnStatus

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="tutor_turns")
    exercise = models.ForeignKey(
        Exercise, on_delete=models.SET_NULL, null=True, blank=True, related_name="tutor_turns"
    )
    attempt = models.ForeignKey(
        ExerciseAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tutor_turns",
    )
    # Project coach turns: a project (and the stage being worked on), never an exercise.
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coach_turns",
    )
    project_stage = models.ForeignKey(
        "projects.ProjectStage",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coach_turns",
    )

    requested_intent = models.CharField(max_length=16, choices=Intent.choices)
    response_kind = models.CharField(max_length=16, choices=ResponseKind.choices, blank=True)
    user_message = models.TextField(blank=True)
    assistant_message = models.TextField(blank=True)
    should_retry = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=TurnStatus.choices, default=TurnStatus.PENDING)

    provider = models.CharField(max_length=32, blank=True)
    model = models.CharField(max_length=100, blank=True)
    prompt_version = models.PositiveSmallIntegerField()
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    provider_response_id = models.CharField(max_length=128, blank=True)
    error_code = models.SlugField(max_length=64, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(requested_intent__in=Intent.values), name="ai_tutor_turn_intent"
            ),
            models.CheckConstraint(
                condition=Q(response_kind="") | Q(response_kind__in=ResponseKind.values),
                name="ai_tutor_turn_kind",
            ),
            models.CheckConstraint(
                condition=Q(status__in=TurnStatus.values), name="ai_tutor_turn_status"
            ),
            # The reservation: at most one in-flight tutor request per learner and exercise,
            # so two requests can never both advance help from the same state.
            models.UniqueConstraint(
                fields=["enrollment", "exercise"],
                condition=Q(status=TurnStatus.PENDING, exercise__isnull=False),
                name="ai_tutor_turn_one_pending_exercise",
            ),
            models.UniqueConstraint(
                fields=["enrollment", "project"],
                condition=Q(status=TurnStatus.PENDING, project__isnull=False),
                name="ai_tutor_turn_one_pending_project",
            ),
            models.CheckConstraint(
                condition=Q(project__isnull=True) | Q(exercise__isnull=True, attempt__isnull=True),
                name="ai_tutor_turn_project_or_exercise",
            ),
            models.CheckConstraint(
                condition=Q(project_stage__isnull=True) | Q(project__isnull=False),
                name="ai_tutor_turn_stage_needs_project",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "created_at"], name="ai_tutor_turn_recent"),
            models.Index(
                fields=["enrollment", "project", "status", "created_at"],
                name="ai_tutor_turn_project",
            ),
            models.Index(
                fields=["enrollment", "status", "created_at"], name="ai_tutor_turn_history"
            ),
        ]

    def __str__(self) -> str:
        return f"Tutor turn {self.pk} · {self.requested_intent} · {self.status}"


class TutorExerciseState(models.Model):
    """AI help given on one exercise since the learner's most recent attempt at it."""

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="tutor_exercise_states"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="tutor_exercise_states"
    )
    hint_level = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(MAX_HINT_LEVEL)]
    )
    used_explanation = models.BooleanField(default=False)
    used_solution = models.BooleanField(default=False)
    last_attempt = models.ForeignKey(
        ExerciseAttempt, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "exercise"], name="ai_tutor_state_unique_exercise"
            ),
            models.CheckConstraint(
                condition=Q(hint_level__lte=MAX_HINT_LEVEL), name="ai_tutor_state_hint_level"
            ),
        ]

    def __str__(self) -> str:
        return f"Tutor help · {self.exercise_id} · level {self.hint_level}"
