from pathlib import Path

from django.test import TestCase

from apps.attempts.models import AttemptStatus, ExerciseAttempt
from apps.attempts.tests.helpers import SECRET_OPTION, AttemptFixtures


class DomainNeutralAttemptTests(AttemptFixtures, TestCase):
    def test_one_service_records_every_subject(self) -> None:
        python = self.record(self.mcq, SECRET_OPTION)
        english = self.record(self.translation, "Hello!")
        maths_right = self.record(self.numeric, "4321.26")
        maths_wrong = self.record(self.numeric, 4000)

        self.assertEqual(
            [
                (a.enrollment.world.title, a.status)
                for a in (python, english, maths_right, maths_wrong)
            ],
            [
                ("Python Foundations", AttemptStatus.CORRECT),
                ("English A1", AttemptStatus.REVIEW_REQUIRED),
                ("Maths Foundations", AttemptStatus.CORRECT),
                ("Maths Foundations", AttemptStatus.INCORRECT),
            ],
        )
        self.assertEqual([a.attempt_number for a in (maths_right, maths_wrong)], [1, 2])
        self.assertEqual(english.enrollment, self.english_enrollment)
        self.assertEqual(ExerciseAttempt.objects.count(), 4)

    def test_attempt_code_has_no_subject_logic(self) -> None:
        package = Path(__file__).resolve().parent.parent
        for name in ("models.py", "services.py", "mistakes.py", "selectors.py", "views.py"):
            source = (package / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                for word in ("python-foundations", "slug ==", "english", "maths"):
                    self.assertNotIn(word, source.lower())
