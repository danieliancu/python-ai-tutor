from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.attempts.models import AttemptStatus
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.models import ConceptState
from apps.learner_intelligence.tests.helpers import IntelligenceFixtures
from apps.python_runner.tests.fakes import outcome


class DomainNeutralIntelligenceTests(IntelligenceFixtures, TestCase):
    def test_one_engine_for_python_english_and_maths(self) -> None:
        # Python: CODE / FIX (Docker-free fake runner).
        self.use_python_backend(lambda *a: outcome("done\n"))
        python_fix = make_exercise(
            self.mcq.lesson, response_type=ResponseType.CODE, learning_mode=LearningMode.FIX
        )
        # English: MULTIPLE_CHOICE / COMPLETE.
        english_choice = make_exercise(
            self.translation.lesson,
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.COMPLETE,
            content={"options": [{"id": "is", "text": "is"}, {"id": "are", "text": "are"}]},
            evaluation_spec={"correct_option": "is"},
        )
        # Maths: NUMERIC / CREATE (self.numeric).

        for _ in range(3):
            self.record(python_fix, "print('done')")
            self.record(english_choice, "is")
            self.record(self.numeric, "4321.25")
        self.record(self.numeric, 1)

        python = ConceptState.objects.get(enrollment=self.enrollment)
        english = ConceptState.objects.get(enrollment=self.english_enrollment)
        maths = ConceptState.objects.get(enrollment=self.maths_enrollment)

        self.assertEqual(
            (python.mastery_score, python.mastery_band), (Decimal("90.00"), "mastered")
        )
        self.assertEqual(
            (english.mastery_score, english.mastery_band), (Decimal("80.00"), "practising")
        )
        self.assertEqual((maths.evidence_count, maths.correct_count), (4, 3))
        self.assertEqual(maths.mastery_band, "practising")
        self.assertEqual(
            [s.mode_states.get().learning_mode for s in (python, english, maths)],
            ["fix", "complete", "create"],
        )
        self.assertEqual(python.concept, self.concept)
        self.assertEqual(english.concept, self.english_concept)
        self.assertEqual(maths.concept, self.maths_concept)

    def test_review_required_subjects_stay_unjudged(self) -> None:
        attempt = self.record(self.translation, "Hello!")
        self.assertEqual(attempt.status, AttemptStatus.REVIEW_REQUIRED)
        state = ConceptState.objects.get(enrollment=self.english_enrollment)
        self.assertEqual((state.mastery_band, state.evidence_count), ("not_started", 0))

    def test_intelligence_code_has_no_subject_logic(self) -> None:
        package = Path(__file__).resolve().parent.parent
        names = [
            "models.py",
            "scoring.py",
            "services.py",
            "selectors.py",
            "presentation.py",
            "views.py",
            "admin.py",
            "management/commands/rebuild_learner_intelligence.py",
        ]
        for name in names:
            source = (package / name).read_text(encoding="utf-8").lower()
            with self.subTest(file=name):
                for word in ("python-foundations", "slug ==", "english", "maths", "python"):
                    self.assertNotIn(word, source)
