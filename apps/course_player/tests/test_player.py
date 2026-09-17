from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.attempts.tests.helpers import SECRET_OPTION
from apps.course_player.tests.helpers import PlayerFixtures, page_config
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill
from apps.exercises.models import Exercise
from apps.exercises.tests.helpers import make_exercise
from apps.learner_intelligence.models import ConceptState
from apps.next_action.engine import next_action_for_enrollment

DEMO_VALUES = (
    "7,840",
    "Level </span>14",
    "31%",
    "Demo preview",
    "Build a Number Analyzer",
    "Look again at the loop condition",
    "Print only numbers greater than 10",
    "Preview Challenge",
)


class PlayerContentTests(PlayerFixtures, TestCase):
    def test_default_exercise_comes_from_next_best_action(self) -> None:
        decision = next_action_for_enrollment(self.enrollment)
        response = self.open()
        self.assertEqual(response.context["player"]["exercise"]["id"], decision.exercise_id)
        self.assertEqual(page_config(response)["exercise"]["id"], decision.exercise_id)

    def test_next_best_action_changes_the_default(self) -> None:
        self.assertEqual(self.open().context["player"]["exercise"]["id"], self.mcq.pk)
        # Recognition succeeded, so the engine moves on to the "complete" mode (the gap).
        self.record(self.mcq, SECRET_OPTION)
        decision = next_action_for_enrollment(self.enrollment)
        self.assertEqual(decision.exercise_id, self.gap.pk)
        self.assertEqual(self.open().context["player"]["exercise"]["id"], self.gap.pk)

    def test_no_demo_data_for_real_learners(self) -> None:
        response = self.open()
        html = response.content.decode()
        for value in DEMO_VALUES:
            with self.subTest(value=value):
                self.assertNotIn(value, html)
        progress = response.context["progress"]
        self.assertEqual(
            (progress["xp"], progress["level"], progress["streak_days"]), ("—", "—", 0)
        )
        self.assertEqual(progress["mastery"], 0)
        self.assertNotIn("Loops", [skill["name"] for skill in response.context["skills"]])

    def test_header_matches_the_curriculum(self) -> None:
        second = make_lesson(self.gap.lesson.concept, title="Second lesson")
        extra = make_exercise(
            second,
            response_type="multiple_choice",
            content={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            evaluation_spec={"correct_option": "a"},
        )
        response = self.open(extra)
        lesson = response.context["lesson"]
        self.assertEqual(lesson["course"], self.python_world.title)
        self.assertEqual(lesson["title"], "Second lesson")
        self.assertEqual((lesson["number"], lesson["total"]), (2, 2))
        self.assertEqual(lesson["exercise_number"], 1)
        self.assertContains(response, "Lesson 2 of 2")
        self.assertContains(response, '<h1 id="lesson-title">Second lesson</h1>', html=True)
        gap = self.open(self.gap).context["lesson"]
        self.assertEqual((gap["number"], gap["exercise_number"]), (1, 2))
        self.assertEqual(response.context["progress"]["current_skill"], self.concept.skill.title)

    def test_account_menu_uses_the_learner_name(self) -> None:
        self.profile.preferred_name = "Dani"
        self.profile.save()
        response = self.open()
        self.assertContains(response, 'aria-label="Account menu for Dani"')
        self.assertNotContains(response, "signin-link")

    def test_course_complete_state(self) -> None:
        ConceptState.objects.create(
            enrollment=self.enrollment,
            concept=self.concept,
            mastery_score=95,
            mastery_band="mastered",
            trend="stable",
            evidence_count=5,
            correct_count=5,
        )
        decision = next_action_for_enrollment(self.enrollment)
        self.assertEqual(decision.action_type, "course_complete")
        response = self.open()
        self.assertEqual(response.context["player"]["state"], "course_complete")
        self.assertIsNone(response.context["player"]["exercise"])
        self.assertContains(response, "Course complete")
        self.assertNotContains(response, "data-exercise-form")
        self.assertNotContains(response, "Lesson 0 of")
        self.assertIsNone(page_config(response)["exercise"])

    def test_no_available_action_state(self) -> None:
        Exercise.objects.filter(lesson__concept__skill__world=self.python_world).update(
            is_published=False
        )
        response = self.open()
        self.assertEqual(response.context["player"]["state"], "no_action")
        self.assertContains(response, "There&#x27;s no available next exercise right now.")
        self.assertNotContains(response, "data-exercise-form")

    def test_world_without_exercises(self) -> None:
        Exercise.objects.filter(lesson__concept__skill__world=self.maths_world).delete()
        response = self.open(world=self.maths_world)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["player"]["state"], "no_action")

    def test_query_count_is_bounded(self) -> None:
        with CaptureQueriesContext(connection) as small:
            self.open()
        for _ in range(8):
            concept = make_concept(make_skill(self.python_world))
            make_exercise(
                make_lesson(concept),
                response_type="multiple_choice",
                content={"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
                evaluation_spec={"correct_option": "a"},
            )
        with CaptureQueriesContext(connection) as large:
            self.open()
        self.assertEqual(len(small), len(large))
        self.assertLess(len(large), 60)
