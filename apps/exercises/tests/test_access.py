from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import make_user
from apps.exercises.access import (
    accessible_exercises,
    learner_can_access_exercise,
    learner_can_access_world,
)
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile


class AccessPolicyTests(TestCase):
    def setUp(self) -> None:
        python_lesson = make_lesson_chain("Python Foundations")
        english_lesson = make_lesson_chain("English A1")
        self.python = python_lesson.concept.skill.world
        self.english = english_lesson.concept.skill.world
        self.python_exercise = make_exercise(python_lesson)
        self.english_exercise = make_exercise(
            english_lesson,
            response_type=ResponseType.TRANSLATION,
            learning_mode=LearningMode.CREATE,
        )
        self.daniel = make_user("daniel")
        self.profile = LearnerProfile.objects.create(user=self.daniel)

    def enroll(self, world, status=EnrollmentStatus.ACTIVE) -> Enrollment:
        return Enrollment.objects.create(learner=self.profile, world=world, status=status)

    def can_access(self, user, exercise) -> bool:
        return learner_can_access_exercise(user, exercise)

    def test_anonymous_has_no_access(self) -> None:
        anonymous = AnonymousUser()
        self.assertFalse(learner_can_access_world(anonymous, self.python))
        self.assertFalse(self.can_access(anonymous, self.python_exercise))
        self.assertFalse(accessible_exercises(anonymous).exists())

    def test_no_enrollment_no_access(self) -> None:
        self.assertFalse(learner_can_access_world(self.daniel, self.python))
        self.assertFalse(self.can_access(self.daniel, self.python_exercise))

    def test_user_without_learner_profile_has_no_access(self) -> None:
        stranger = make_user("stranger")
        self.assertFalse(learner_can_access_world(stranger, self.python))
        self.assertFalse(accessible_exercises(stranger).exists())

    def test_access_by_enrollment_status(self) -> None:
        enrollment = self.enroll(self.python)
        expectations = {
            EnrollmentStatus.ACTIVE: True,
            EnrollmentStatus.COMPLETED: True,
            EnrollmentStatus.PAUSED: False,
        }
        for status, allowed in expectations.items():
            with self.subTest(status=status):
                enrollment.status = status
                enrollment.save()
                self.assertIs(learner_can_access_world(self.daniel, self.python), allowed)
                self.assertIs(self.can_access(self.daniel, self.python_exercise), allowed)

    def test_python_learner_cannot_reach_english(self) -> None:
        self.enroll(self.python)
        self.assertTrue(self.can_access(self.daniel, self.python_exercise))
        self.assertFalse(self.can_access(self.daniel, self.english_exercise))
        self.assertFalse(learner_can_access_world(self.daniel, self.english))
        self.assertEqual(list(accessible_exercises(self.daniel)), [self.python_exercise])

    def test_other_learners_enrollments_do_not_count(self) -> None:
        ana = make_user("ana")
        Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=ana), world=self.english
        )
        self.assertFalse(self.can_access(self.daniel, self.english_exercise))
        self.assertTrue(self.can_access(ana, self.english_exercise))

    def test_multiple_enrollments(self) -> None:
        self.enroll(self.python)
        self.enroll(self.english, EnrollmentStatus.COMPLETED)
        self.assertTrue(self.can_access(self.daniel, self.python_exercise))
        self.assertTrue(self.can_access(self.daniel, self.english_exercise))
        self.assertEqual(
            set(accessible_exercises(self.daniel)), {self.python_exercise, self.english_exercise}
        )

    def test_accessible_exercises_has_no_duplicates(self) -> None:
        self.enroll(self.python)
        make_exercise(self.python_exercise.lesson)
        ids = list(accessible_exercises(self.daniel).values_list("pk", flat=True))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 2)

    def test_enrollment_does_not_reveal_unpublished_content(self) -> None:
        self.enroll(self.python)
        hidden = make_exercise(self.python_exercise.lesson, is_published=False)
        self.assertFalse(self.can_access(self.daniel, hidden))
        self.python.is_published = False
        self.python.save()
        self.assertFalse(self.can_access(self.daniel, self.python_exercise))
        # The enrollment itself remains valid.
        self.assertTrue(learner_can_access_world(self.daniel, self.python))

    def test_staff_are_not_silently_granted_access(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.assertFalse(learner_can_access_world(admin, self.python))
        self.assertFalse(self.can_access(admin, self.python_exercise))
