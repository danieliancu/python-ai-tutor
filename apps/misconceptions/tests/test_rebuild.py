from io import StringIO

from django.core.management import CommandError, call_command
from django.forms.models import model_to_dict
from django.test import TestCase

from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.tests.helpers import COMPARISON_REFERENCE, MisconceptionFixtures

DAY = 24 * 60


def derived() -> dict:
    evidence = sorted(
        (
            row["attempt"],
            row["code"],
            row["kind"],
            row["source"],
            row["strength"],
            str(row["details"]),
        )
        for row in (model_to_dict(e, exclude=["id"]) for e in MisconceptionEvidence.objects.all())
    )
    states = sorted(
        tuple(sorted(model_to_dict(s, exclude=["id"]).items()))
        for s in MisconceptionState.objects.all()
    )
    return {"evidence": evidence, "states": states}


class RebuildCommandTests(MisconceptionFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.wrong(self.range_gap, 0, submitted_answer="5")
        self.wrong(self.range_gap, DAY, submitted_answer="5")
        for day in (2, 3, 4):
            self.right(self.range_gap, day * DAY)
        self.wrong(
            self.comparison, 5 * DAY, submitted_answer=COMPARISON_REFERENCE.replace(">", "<")
        )
        self.wrong(self.article, 0, enrollment=self.english_enrollment)
        self.wrong(self.sign, 0, enrollment=self.maths_enrollment)

    def rebuild(self, *args) -> str:
        out = StringIO()
        call_command("rebuild_misconceptions", *args, stdout=out)
        return out.getvalue()

    def test_rebuild_recreates_everything_and_is_idempotent(self) -> None:
        output = self.rebuild()
        self.assertIn("Evidence: 19 created, 0 updated, 0 deleted", output)
        self.assertIn("States: 6 created, 0 updated, 0 unchanged, 0 deleted", output)
        self.assertIn("(0 active, 4 watch, 2 resolved)", output)
        self.assertIn("for 3 learner concepts", output)
        reference = derived()
        self.assertEqual(
            MisconceptionState.objects.get(code="range-exclusive-stop").status, "resolved"
        )

        MisconceptionEvidence.objects.all().delete()
        MisconceptionState.objects.all().delete()
        self.rebuild()
        self.assertEqual(derived(), reference)

        output = self.rebuild()
        self.assertIn("Evidence: 0 created, 0 updated, 0 deleted", output)
        self.assertIn("States: 0 created, 0 updated, 6 unchanged, 0 deleted", output)
        self.assertEqual(derived(), reference)

    def test_rebuild_repairs_tampering(self) -> None:
        self.rebuild()
        reference = derived()
        MisconceptionState.objects.update(status="active", confidence_score=99)
        MisconceptionEvidence.objects.filter(source="exercise_tag").update(strength=1)
        MisconceptionEvidence.objects.filter(kind="counter").delete()
        MisconceptionState.objects.create(
            enrollment=self.english_enrollment,
            concept=self.english_concept,
            code="made-up",
            status="active",
            confidence_score=90,
            first_seen_at=self.at(0),
            last_seen_at=self.at(0),
        )
        output = self.rebuild()
        self.assertIn("1 deleted", output)
        self.assertEqual(derived(), reference)

    def test_stale_pairs_are_removed(self) -> None:
        self.rebuild()
        MisconceptionState.objects.create(
            enrollment=self.english_enrollment,
            concept=self.concept,
            code="off-by-one",
            status="watch",
            confidence_score=10,
            first_seen_at=self.at(0),
            last_seen_at=self.at(0),
        )
        output = self.rebuild()
        self.assertIn("1 deleted", output)
        self.assertEqual(MisconceptionState.objects.filter(concept=self.concept).count(), 4)

    def test_filters(self) -> None:
        output = self.rebuild("--enrollment-id", str(self.maths_enrollment.pk))
        self.assertIn("for 1 learner concepts", output)
        self.assertEqual(
            list(MisconceptionState.objects.values_list("code", flat=True)), ["sign-error"]
        )
        self.rebuild("--world-slug", self.english_world.slug)
        self.assertEqual(MisconceptionState.objects.count(), 2)
        # A filtered rebuild never touches states outside its scope.
        self.rebuild("--world-slug", self.python_world.slug)
        self.assertEqual(MisconceptionState.objects.count(), 6)

    def test_unknown_filters_are_rejected(self) -> None:
        with self.assertRaises(CommandError):
            self.rebuild("--world-slug", "missing")
        with self.assertRaises(CommandError):
            self.rebuild("--enrollment-id", "999999")
