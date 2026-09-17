from datetime import timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.forms.models import model_to_dict
from django.test import TestCase

from apps.exercises.models import LearningMode
from apps.learner_intelligence.models import ConceptModeState, ConceptState
from apps.learner_intelligence.services import refresh_concept_state
from apps.learner_intelligence.tests.helpers import (
    BASE_TIME,
    CORRECT,
    INCORRECT,
    IntelligenceFixtures,
)


def all_states() -> list[dict]:
    rows = []
    for state in ConceptState.objects.order_by("enrollment_id", "concept_id"):
        data = model_to_dict(state, exclude=["id"])
        data["modes"] = [
            model_to_dict(mode, exclude=["id", "concept_state"])
            for mode in state.mode_states.order_by("learning_mode")
        ]
        rows.append(data)
    return rows


class RebuildCommandTests(IntelligenceFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        day = timedelta(days=1)
        for index, (mode, status) in enumerate(
            [
                (LearningMode.RECOGNISE, CORRECT),
                (LearningMode.COMPLETE, INCORRECT),
                (LearningMode.FIX, CORRECT),
                (LearningMode.CREATE, CORRECT),
                (LearningMode.FIX, CORRECT),
                (LearningMode.CREATE, INCORRECT),
            ]
        ):
            self.make_attempt(
                self.by_mode[mode],
                status,
                at=BASE_TIME + index * day,
                duration_seconds=45 + index * 10,
                hint_level=index % 2,
            )
        for index in range(3):
            self.make_attempt(
                self.numeric,
                CORRECT,
                enrollment=self.maths_enrollment,
                at=BASE_TIME + timedelta(minutes=index),
            )

    def rebuild(self, *args) -> str:
        out = StringIO()
        call_command("rebuild_learner_intelligence", *args, stdout=out)
        return out.getvalue()

    def test_rebuild_recreates_deleted_states(self) -> None:
        expected = [
            refresh_concept_state(self.enrollment, self.concept),
            refresh_concept_state(self.maths_enrollment, self.maths_concept),
        ]
        reference = all_states()
        self.assertEqual(len(expected), 2)

        ConceptState.objects.all().delete()
        output = self.rebuild()
        self.assertIn("2 created, 0 updated, 0 unchanged, 0 stale deleted (2 total)", output)
        self.assertEqual(all_states(), reference)
        self.assertEqual(ConceptModeState.objects.count(), 5)  # 4 modes + 1

        output = self.rebuild()
        self.assertIn("0 created, 0 updated, 2 unchanged, 0 stale deleted (2 total)", output)
        self.assertEqual(all_states(), reference)
        self.assertEqual(ConceptState.objects.count(), 2)

    def test_rebuild_repairs_tampered_and_outdated_state(self) -> None:
        self.rebuild()
        reference = all_states()
        ConceptState.objects.filter(concept=self.concept).update(
            mastery_score=100, algorithm_version=0, mastery_band="mastered"
        )
        ConceptModeState.objects.filter(learning_mode=LearningMode.FIX).delete()
        output = self.rebuild()
        self.assertIn("1 updated", output)
        self.assertEqual(all_states(), reference)
        self.assertEqual(set(ConceptState.objects.values_list("algorithm_version", flat=True)), {1})

    def test_stale_states_are_removed(self) -> None:
        self.rebuild()
        orphan = ConceptState.objects.create(
            enrollment=self.english_enrollment, concept=self.english_concept
        )
        output = self.rebuild()
        self.assertIn("1 stale deleted", output)
        self.assertFalse(ConceptState.objects.filter(pk=orphan.pk).exists())

    def test_filters(self) -> None:
        output = self.rebuild("--enrollment-id", str(self.maths_enrollment.pk))
        self.assertIn("(1 total)", output)
        self.assertEqual(
            list(ConceptState.objects.values_list("enrollment_id", flat=True)),
            [self.maths_enrollment.pk],
        )
        output = self.rebuild("--world-slug", self.python_world.slug)
        self.assertIn("1 created", output)
        self.assertEqual(ConceptState.objects.count(), 2)

        # A filtered rebuild never deletes states outside its scope.
        self.rebuild("--world-slug", self.english_world.slug)
        self.assertEqual(ConceptState.objects.count(), 2)

    def test_unknown_filters_are_rejected(self) -> None:
        with self.assertRaises(CommandError):
            self.rebuild("--world-slug", "no-such-world")
        with self.assertRaises(CommandError):
            self.rebuild("--enrollment-id", "999999")
