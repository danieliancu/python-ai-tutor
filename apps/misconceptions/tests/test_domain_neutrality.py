from pathlib import Path

from django.test import TestCase

from apps.misconceptions.definitions import title_for
from apps.misconceptions.models import MisconceptionEvidence, MisconceptionState
from apps.misconceptions.tests.helpers import MisconceptionFixtures

GENERIC_MODULES = (
    "models.py",
    "definitions.py",
    "evidence.py",
    "scoring.py",
    "services.py",
    "selectors.py",
    "presentation.py",
    "admin.py",
    "management/commands/rebuild_misconceptions.py",
)


class DomainNeutralMisconceptionTests(MisconceptionFixtures, TestCase):
    def test_one_engine_for_every_subject(self) -> None:
        self.record(self.range_gap, "5")
        self.record(self.range_gap, "5")
        for _ in range(3):
            self.record(self.article, "b")  # English multiple choice
        self.record(self.sign, "-5")  # Maths numeric
        self.record(self.sign, "-5")

        states = {(s.enrollment_id, s.code): s.status for s in MisconceptionState.objects.all()}
        self.assertEqual(
            states,
            {
                (self.enrollment.pk, "off-by-one"): "active",
                (self.enrollment.pk, "range-exclusive-stop"): "active",
                (self.english_enrollment.pk, "article-omission"): "watch",
                (self.maths_enrollment.pk, "sign-error"): "watch",
            },
        )
        english = MisconceptionState.objects.get(code="article-omission")
        self.assertEqual(
            (english.concept, english.positive_evidence_count), (self.english_concept, 3)
        )
        # Only generic candidate evidence exists outside Python.
        self.assertEqual(
            set(
                MisconceptionEvidence.objects.exclude(
                    attempt__enrollment=self.enrollment
                ).values_list("source", flat=True)
            ),
            {"exercise_tag"},
        )
        self.assertEqual(title_for("article-omission"), "Article omission")

    def test_generic_modules_have_no_subject_logic(self) -> None:
        package = Path(__file__).resolve().parent.parent
        for name in GENERIC_MODULES:
            source = (package / name).read_text(encoding="utf-8").lower()
            with self.subTest(file=name):
                for word in ("python", "english", "maths", "slug ==", "range(", "ast."):
                    self.assertNotIn(word, source)
