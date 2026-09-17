"""Learner intelligence consumes the real Python Foundations pack unchanged (Docker-free)."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.attempts.services import record_attempt
from apps.curriculum.models import Concept, Skill, World
from apps.exercises.models import Exercise
from apps.learner_intelligence.models import ConceptState
from apps.learner_intelligence.presentation import student_state_for_enrollment
from apps.learner_intelligence.tests.helpers import IntelligenceFixtures
from apps.learners.models import Enrollment


class PythonPackIntelligenceTests(IntelligenceFixtures, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def setUp(self) -> None:
        super().setUp()
        self.world = World.objects.get(slug="python-foundations")
        self.pack_enrollment = Enrollment.objects.create(learner=self.profile, world=self.world)

    def test_pack_is_unchanged(self) -> None:
        self.assertEqual(Skill.objects.filter(world=self.world).count(), 11)
        self.assertEqual(Concept.objects.filter(skill__world=self.world).count(), 53)
        self.assertEqual(
            Exercise.objects.filter(lesson__concept__skill__world=self.world).count(), 147
        )

    def test_attempts_on_the_pack_build_student_state(self) -> None:
        exercise = Exercise.objects.get(slug="ten-or-more")
        record_attempt(user=self.user, exercise=exercise, answer="a")
        record_attempt(user=self.user, exercise=exercise, answer="b")

        state = ConceptState.objects.get(enrollment=self.pack_enrollment)
        self.assertEqual(state.concept, exercise.lesson.concept)
        self.assertEqual((state.evidence_count, state.correct_count), (2, 1))

        data = student_state_for_enrollment(self.pack_enrollment)
        self.assertEqual(data["summary"]["concepts_total"], 53)
        self.assertEqual(data["summary"]["concepts_started"], 1)
        self.assertEqual(len(data["skills"]), 11)
        self.assertEqual(len(data["concepts"]), 53)

        call_command("rebuild_learner_intelligence", stdout=StringIO())
        self.assertEqual(ConceptState.objects.filter(enrollment=self.pack_enrollment).count(), 1)
