from datetime import UTC, datetime, timedelta
from decimal import Decimal

from apps.accounts.tests.helpers import make_user
from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.curriculum.models import ConceptPrerequisite, SkillPrerequisite
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill, make_world
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.models import ConceptModeState, ConceptState
from apps.learner_intelligence.scoring import mastery_band
from apps.learners.models import Enrollment, LearnerProfile
from apps.misconceptions.models import MisconceptionState
from apps.next_action.types import ActiveMisconception, ConceptContext

NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
ALL_MODES = tuple(LearningMode.values)


def context(**fields) -> ConceptContext:
    """A pure ConceptContext with sensible defaults (started, 70 mastery, four modes)."""
    values = {
        "concept_id": 1,
        "skill_id": 1,
        "skill_order": 1,
        "concept_order": 1,
        "started": True,
        "has_state": True,
        "mastery": 70.0,
        "band": "practising",
        "available_modes": frozenset(ALL_MODES),
        "mode_success": frozenset(ALL_MODES),
        "mode_performance": dict.fromkeys(ALL_MODES, 90.0),
        "prerequisites_ready": True,
    }
    values.update(fields)
    return ConceptContext(**values)


def active(code: str, confidence: float = 70.0, at: datetime = NOW) -> ActiveMisconception:
    return ActiveMisconception(code, confidence, at)


def choice(**fields):
    fields.setdefault("response_type", ResponseType.MULTIPLE_CHOICE)
    fields.setdefault("content", {"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]})
    tags = fields.pop("tags", None)
    spec = {"correct_option": "a"}
    if tags:
        spec["misconceptions"] = list(tags)
    fields.setdefault("evaluation_spec", spec)
    return fields


class WorldFixtures:
    """A small generic World: skills A (concepts a1, a2) and B (b1), one learner."""

    world_title = "Generic World"

    def setUp(self) -> None:
        super().setUp()
        self.user = make_user("learner")
        self.profile = LearnerProfile.objects.create(user=self.user)
        self.world = make_world(self.world_title)
        self.enrollment = Enrollment.objects.create(learner=self.profile, world=self.world)
        self.skill_a = make_skill(self.world, "Skill A")
        self.skill_b = make_skill(self.world, "Skill B")
        self.a1 = make_concept(self.skill_a, "A one")
        self.a2 = make_concept(self.skill_a, "A two")
        self.b1 = make_concept(self.skill_b, "B one")
        self.lessons = {c.pk: make_lesson(c) for c in (self.a1, self.a2, self.b1)}
        self.ex = {
            c.pk: make_exercise(
                self.lessons[c.pk], learning_mode=LearningMode.RECOGNISE, **choice()
            )
            for c in (self.a1, self.a2, self.b1)
        }

    # curriculum
    def exercise(self, concept, mode=LearningMode.RECOGNISE, lesson=None, **fields):
        return make_exercise(
            lesson or self.lessons[concept.pk], learning_mode=mode, **choice(**fields)
        )

    def requires(self, concept, prerequisite) -> None:
        ConceptPrerequisite.objects.create(concept=concept, prerequisite=prerequisite)

    def skill_requires(self, skill, prerequisite) -> None:
        SkillPrerequisite.objects.create(skill=skill, prerequisite=prerequisite)

    # learner state
    def state(
        self,
        concept,
        mastery: float,
        *,
        enrollment=None,
        band: str | None = None,
        review_due_at: datetime | None = None,
        trend: str = "stable",
        retention: float | None = None,
        modes: dict | None = None,
    ) -> ConceptState:
        modes = modes or {}
        advanced = any(
            correct and mode in ("fix", "create") for mode, (_, correct) in modes.items()
        )
        state = ConceptState.objects.create(
            enrollment=enrollment or self.enrollment,
            concept=concept,
            mastery_score=Decimal(str(mastery)),
            mastery_band=band or mastery_band(mastery, 3, advanced),
            trend=trend,
            retention_score=None if retention is None else Decimal(str(retention)),
            stability_days=None if review_due_at is None else 3,
            # Far enough ahead that views using the real clock see nothing due.
            review_due_at=review_due_at or NOW + timedelta(days=3650),
            evidence_count=3,
            correct_count=3,
            last_attempt_at=NOW - timedelta(days=1),
        )
        for mode, (performance, correct) in modes.items():
            ConceptModeState.objects.create(
                concept_state=state,
                learning_mode=mode,
                performance_score=Decimal(str(performance)),
                attempt_count=max(correct, 1),
                correct_count=correct,
                last_attempt_at=NOW - timedelta(days=1),
            )
        return state

    def misconception(
        self,
        concept,
        code: str,
        status: str = "active",
        confidence: float = 70.0,
        *,
        enrollment=None,
        last_seen_at: datetime = NOW - timedelta(hours=1),
    ) -> MisconceptionState:
        return MisconceptionState.objects.create(
            enrollment=enrollment or self.enrollment,
            concept=concept,
            code=code,
            status=status,
            confidence_score=Decimal(str(confidence)),
            first_seen_at=last_seen_at,
            last_seen_at=last_seen_at,
        )

    def attempt(
        self,
        exercise,
        *,
        enrollment=None,
        at: datetime = NOW - timedelta(hours=2),
        status=AttemptStatus.INCORRECT,
    ):
        enrollment = enrollment or self.enrollment
        number = ExerciseAttempt.objects.filter(enrollment=enrollment, exercise=exercise).count()
        attempt = ExerciseAttempt.objects.create(
            enrollment=enrollment,
            exercise=exercise,
            attempt_number=number + 1,
            status=status,
            score=1.0 if status == AttemptStatus.CORRECT else 0.0,
            is_correct=status == AttemptStatus.CORRECT,
            evaluator="test",
            message="Recorded in a test.",
        )
        ExerciseAttempt.objects.filter(pk=attempt.pk).update(submitted_at=at)
        return attempt

    def other_learner(self, username="other", world=None) -> Enrollment:
        profile = LearnerProfile.objects.create(user=make_user(username))
        return Enrollment.objects.create(learner=profile, world=world or self.world)
