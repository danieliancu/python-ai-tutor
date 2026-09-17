from datetime import UTC, datetime, timedelta

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.attempts.tests.helpers import AttemptFixtures
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.scoring import Evidence

BASE_TIME = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)

CORRECT = AttemptStatus.CORRECT
INCORRECT = AttemptStatus.INCORRECT


def ev(
    correct: bool = True,
    mode: str = LearningMode.COMPLETE,
    minutes: float = 0,
    *,
    status: str | None = None,
    **fields,
) -> Evidence:
    """Evidence at BASE_TIME + ``minutes``. Scoring sequences are newest first."""
    if status is None:
        status = CORRECT if correct else INCORRECT
    judged = status in (CORRECT, INCORRECT)
    fields.setdefault("score", (1.0 if correct else 0.0) if judged else None)
    fields.setdefault("is_correct", correct if judged else None)
    return Evidence(
        status=status,
        submitted_at=BASE_TIME + timedelta(minutes=minutes),
        learning_mode=mode,
        **fields,
    )


def newest_first(*evidence: Evidence) -> list[Evidence]:
    return sorted(evidence, key=lambda e: e.submitted_at, reverse=True)


def series(pattern: str, mode: str = LearningMode.COMPLETE, **fields) -> list[Evidence]:
    """Chronological pattern like "xx111" (x = incorrect, 1 = correct), returned newest first."""
    return newest_first(
        *(ev(char == "1", mode, minutes=index, **fields) for index, char in enumerate(pattern))
    )


class IntelligenceFixtures(AttemptFixtures):
    """AttemptFixtures plus one exercise per learning mode in the Python concept."""

    def setUp(self) -> None:
        super().setUp()
        lesson = self.mcq.lesson
        self.concept = lesson.concept
        self.english_concept = self.translation.lesson.concept
        self.maths_concept = self.numeric.lesson.concept
        self.by_mode = {
            mode: make_exercise(
                lesson,
                response_type=ResponseType.MULTIPLE_CHOICE,
                learning_mode=mode,
                target_seconds=60,
            )
            for mode in LearningMode.values
        }

    def make_attempt(
        self,
        exercise,
        status: str = CORRECT,
        *,
        enrollment=None,
        at: datetime | None = None,
        **fields,
    ) -> ExerciseAttempt:
        """Store an attempt directly with a chosen outcome and timestamp."""
        enrollment = enrollment or self.enrollment
        judged = status in (CORRECT, INCORRECT)
        fields.setdefault("score", (1.0 if status == CORRECT else 0.0) if judged else None)
        fields.setdefault("is_correct", (status == CORRECT) if judged else None)
        number = ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise).count()
        attempt = ExerciseAttempt.objects.create(
            enrollment=enrollment,
            exercise=exercise,
            attempt_number=number + 1,
            status=status,
            evaluator="test",
            message="Recorded in a test.",
            **fields,
        )
        if at is not None:
            ExerciseAttempt.objects.filter(pk=attempt.pk).update(submitted_at=at)
            attempt.refresh_from_db()
        return attempt
