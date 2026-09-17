from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.tests.helpers import TutorFixtures


class TutorModelTests(TutorFixtures, TestCase):
    def test_one_assistance_row_per_exercise(self) -> None:
        TutorExerciseState.objects.create(enrollment=self.enrollment, exercise=self.mcq)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorExerciseState.objects.create(enrollment=self.enrollment, exercise=self.mcq)

    def test_hint_level_is_bounded(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorExerciseState.objects.create(
                enrollment=self.enrollment, exercise=self.gap, hint_level=3
            )

    def test_choice_fields_are_checked(self) -> None:
        for field, value in (
            ("requested_intent", "hack"),
            ("status", "done"),
            ("response_kind", "grade"),
        ):
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                self.old_turn(**{field: value})

    def test_turns_keep_no_prompt_or_payload_fields(self) -> None:
        names = {field.name for field in TutorTurn._meta.get_fields()}
        for forbidden in ("prompt", "instructions", "context", "request", "raw_response"):
            self.assertNotIn(forbidden, names)
        self.assertIn("prompt_version", names)
