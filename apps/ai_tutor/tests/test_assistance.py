from django.test import TestCase

from apps.ai_tutor.assistance import (
    apply_turn,
    assistance_for,
    merge_with_client,
    record_attempt_boundary,
)
from apps.ai_tutor.models import TutorExerciseState
from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.ai_tutor.types import AssistanceState


class AssistanceTests(TutorFixtures, TestCase):
    def test_nothing_recorded_means_no_help(self) -> None:
        self.assertEqual(assistance_for(self.enrollment, self.mcq), AssistanceState())

    def test_apply_turn_follows_the_ladder(self) -> None:
        self.assertEqual(apply_turn(self.enrollment, self.mcq, "guidance"), AssistanceState())
        self.assertEqual(apply_turn(self.enrollment, self.mcq, "hint"), AssistanceState(1))
        self.assertEqual(apply_turn(self.enrollment, self.mcq, "hint"), AssistanceState(1))
        self.assertEqual(apply_turn(self.enrollment, self.mcq, "strong_hint"), AssistanceState(2))
        state = apply_turn(self.enrollment, self.mcq, "explanation")
        self.assertEqual(state, AssistanceState(2, True))
        self.assertEqual(assistance_for(self.enrollment, self.mcq), state)
        self.assertEqual(assistance_for(self.english_enrollment, self.mcq), AssistanceState())

    def test_merge_uses_max_and_or(self) -> None:
        apply_turn(self.enrollment, self.mcq, "hint")
        apply_turn(self.enrollment, self.mcq, "explanation")
        self.assertEqual(
            merge_with_client(
                self.enrollment,
                self.mcq,
                hint_level=0,
                used_explanation=False,
                used_solution=False,
            ),
            {"hint_level": 1, "used_explanation": True, "used_solution": False},
        )
        # The client may report more help than the tutor gave (e.g. other hints).
        self.assertEqual(
            merge_with_client(
                self.enrollment,
                self.mcq,
                hint_level=2,
                used_explanation=False,
                used_solution=True,
            ),
            {"hint_level": 2, "used_explanation": True, "used_solution": True},
        )

    def test_attempt_boundary_resets(self) -> None:
        apply_turn(self.enrollment, self.mcq, "strong_hint")
        apply_turn(self.enrollment, self.mcq, "solution")
        attempt = self.make_attempt(self.mcq)
        record_attempt_boundary(attempt)
        row = TutorExerciseState.objects.get(enrollment=self.enrollment, exercise=self.mcq)
        self.assertEqual(
            (row.hint_level, row.used_explanation, row.used_solution, row.last_attempt),
            (0, False, False, attempt),
        )
        # A first attempt without any tutor help also records the boundary.
        other = self.make_attempt(self.gap)
        record_attempt_boundary(other)
        self.assertEqual(TutorExerciseState.objects.get(exercise=self.gap).last_attempt, other)
