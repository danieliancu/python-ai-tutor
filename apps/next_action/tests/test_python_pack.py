"""Next Best Action on the real Python Foundations pack (Docker-free answers only)."""

import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.helpers import make_user
from apps.attempts.services import record_attempt
from apps.curriculum.models import Concept, Skill, World
from apps.exercises.models import Exercise
from apps.learner_intelligence.models import ConceptState
from apps.learners.models import Enrollment, LearnerProfile
from apps.next_action import constants as c
from apps.next_action.engine import next_action_for_enrollment

WORLD_SLUG = "python-foundations"


class PythonPackNextActionTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_python_exercises", stdout=StringIO())

    def setUp(self) -> None:
        self.user = make_user("learner")
        self.world = World.objects.get(slug=WORLD_SLUG)
        self.enrollment = Enrollment.objects.create(
            learner=LearnerProfile.objects.create(user=self.user), world=self.world
        )

    def exercise(self, slug: str) -> Exercise:
        return Exercise.objects.get(lesson__concept__skill__world=self.world, slug=slug)

    def answer(self, slug: str, *, correct: bool):
        exercise = self.exercise(slug)
        spec = exercise.evaluation_spec
        if "correct_option" in spec:
            options = [o["id"] for o in exercise.content["options"]]
            answer = (
                spec["correct_option"]
                if correct
                else next(o for o in options if o != spec["correct_option"])
            )
        else:
            answer = spec["accepted_answers"][0] if correct else "definitely wrong"
        return record_attempt(user=self.user, exercise=exercise, answer=answer)

    def decide(self, now):
        return next_action_for_enrollment(self.enrollment, now=now)

    def concept(self, slug: str) -> Concept:
        return Concept.objects.get(skill__world=self.world, slug=slug)

    def test_pack_is_unchanged(self) -> None:
        self.assertEqual(Skill.objects.filter(world=self.world).count(), 11)
        self.assertEqual(Concept.objects.filter(skill__world=self.world).count(), 53)
        self.assertEqual(
            Exercise.objects.filter(lesson__concept__skill__world=self.world).count(), 147
        )

    def test_progression_through_the_pack(self) -> None:
        start = timezone.now()

        # 1. A fresh learner starts with the first authored concept, recognition first.
        fresh = self.decide(start)
        self.assertEqual(
            (fresh.action_type, fresh.concept_id), (c.LEARN, self.concept("running-python").pk)
        )
        exercise = Exercise.objects.get(pk=fresh.exercise_id)
        self.assertEqual(exercise.slug, "top-to-bottom-order")
        self.assertTrue(exercise.is_published)
        self.assertEqual(fresh.target_learning_mode, "recognise")

        # 2. Basic competence (65) unlocks the next concept without demanding mastery.
        for _ in range(3):
            self.answer("top-to-bottom-order", correct=True)
        state = ConceptState.objects.get(enrollment=self.enrollment)
        self.assertEqual(float(state.mastery_score), 65.0)
        now = timezone.now()
        after_basics = self.decide(now)
        self.assertEqual(
            (after_basics.action_type, after_basics.concept_id),
            (c.LEARN, self.concept("print-and-output").pk),
        )
        self.assertEqual(
            Exercise.objects.get(pk=after_basics.exercise_id).slug, "print-with-separator"
        )

        # 3. A persistent misconception interrupts progression.
        for _ in range(5):
            self.answer("what-comments-hide", correct=False)
        remediate = self.decide(timezone.now())
        self.assertEqual(
            (remediate.action_type, remediate.concept_id),
            (c.REMEDIATE, self.concept("comments").pk),
        )
        self.assertEqual(remediate.misconception_codes, ("comment-scope",))
        self.assertEqual(Exercise.objects.get(pk=remediate.exercise_id).slug, "what-comments-hide")

        # 4. Once it is resolved enough to stop being active, a due review comes first.
        for _ in range(6):
            self.answer("what-comments-hide", correct=True)
        later = timezone.now() + timedelta(days=4)
        review = self.decide(later)
        self.assertEqual(review.action_type, c.REVIEW)
        self.assertIn(
            review.concept_id, {self.concept("running-python").pk, self.concept("comments").pk}
        )
        self.assertNotEqual(review.action_type, c.REMEDIATE)

    def test_due_review_interrupts_new_content(self) -> None:
        for _ in range(3):
            self.answer("top-to-bottom-order", correct=True)
        review = self.decide(timezone.now() + timedelta(days=4))
        self.assertEqual(
            (review.action_type, review.concept_id),
            (c.REVIEW, self.concept("running-python").pk),
        )
        # Recall is tested in the mode not yet demonstrated (the code exercise).
        self.assertEqual(review.target_learning_mode, "create")

    def test_endpoint_and_debug_command(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("next_action:next_action", args=[self.world.pk]))
        data = response.json()
        self.assertEqual(data["action"], "learn")
        self.assertEqual(data["exercise"]["slug"], "top-to-bottom-order")
        body = json.dumps(data)
        for secret in ("evaluation_spec", "correct_option", "explanation", 'misconceptions": ["'):
            self.assertNotIn(secret, body)

        out = StringIO()
        call_command(
            "explain_next_action",
            str(self.enrollment.pk),
            "--now",
            "2030-01-01T00:00:00+00:00",
            stdout=out,
        )
        printed = json.loads(out.getvalue())
        self.assertEqual(printed["action"], "learn")
        self.assertEqual(printed["internal"], {"priority_tier": 200, "urgency_score": 0.0})
        self.assertNotIn("correct_option", out.getvalue())
