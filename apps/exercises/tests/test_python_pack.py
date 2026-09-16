import json
from collections import Counter, defaultdict
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.curriculum.models import Concept, Skill
from apps.exercises.data.python_foundations import EXERCISES
from apps.exercises.data.python_foundations.builders import GAP_PATTERN
from apps.exercises.models import Exercise, LearningMode, ResponseType
from apps.exercises.presentation import exercise_presentation
from apps.exercises.selectors import published_exercises
from apps.exercises.tests.helpers import make_exercise
from apps.exercises.validation import validate_exercise_json

ALL_MODES = set(LearningMode.values)
PYTHON_RESPONSE_TYPES = {
    ResponseType.CODE,
    ResponseType.MULTIPLE_CHOICE,
    ResponseType.FILL_GAP,
    ResponseType.TEXT,
}
TARGET_SECONDS = {
    LearningMode.RECOGNISE: (20, 60),
    LearningMode.COMPLETE: (30, 120),
    LearningMode.FIX: (60, 180),
    LearningMode.CREATE: (90, 300),
}
KEY_CONCEPTS = [
    "comparison-operators",
    "range",
    "nested-loops",
    "return-values",
    "scope",
    "logic-errors",
    "debugging-workflow",
    "classes-and-objects",
]


def seed(command: str) -> str:
    out = StringIO()
    call_command(command, stdout=out)
    return out.getvalue()


class PackDefinitionTests(SimpleTestCase):
    """Checks on the declarative data, without a database."""

    def test_identity_and_ordering(self) -> None:
        by_lesson = defaultdict(list)
        for exercise in EXERCISES:
            by_lesson[(exercise["skill"], exercise["concept"], exercise["lesson"])].append(exercise)
        for path, items in by_lesson.items():
            with self.subTest(lesson=path):
                slugs = [item["slug"] for item in items]
                self.assertEqual(len(slugs), len(set(slugs)))
                self.assertEqual([item["order"] for item in items], list(range(1, len(items) + 1)))

    def test_every_definition_is_valid_and_serialisable(self) -> None:
        for exercise in EXERCISES:
            with self.subTest(exercise=exercise["slug"]):
                self.assertIn(exercise["response_type"], PYTHON_RESPONSE_TYPES)
                self.assertIn(exercise["learning_mode"], ALL_MODES)
                validate_exercise_json(
                    exercise["response_type"], exercise["content"], exercise["evaluation_spec"]
                )
                json.dumps(exercise)
                self.assertTrue(exercise["title"] and exercise["prompt"])

    def test_target_seconds_fit_the_mode(self) -> None:
        for exercise in EXERCISES:
            low, high = TARGET_SECONDS[exercise["learning_mode"]]
            with self.subTest(exercise=exercise["slug"]):
                self.assertGreaterEqual(exercise["target_seconds"], low)
                self.assertLessEqual(exercise["target_seconds"], high)
        self.assertGreater(len({e["target_seconds"] for e in EXERCISES}), 10)

    def test_multiple_choice_contract(self) -> None:
        for exercise in self.of_type(ResponseType.MULTIPLE_CHOICE):
            with self.subTest(exercise=exercise["slug"]):
                option_ids = [option["id"] for option in exercise["content"]["options"]]
                self.assertIn(exercise["evaluation_spec"]["correct_option"], option_ids)
                self.assertGreaterEqual(len(option_ids), 3)
                self.assertTrue(exercise["evaluation_spec"]["explanation"])

    def test_fill_gap_contract(self) -> None:
        for exercise in self.of_type(ResponseType.FILL_GAP):
            with self.subTest(exercise=exercise["slug"]):
                self.assertEqual(len(GAP_PATTERN.findall(exercise["content"]["template"])), 1)
                spec = exercise["evaluation_spec"]
                self.assertTrue(spec["accepted_answers"])
                self.assertTrue(all(isinstance(a, str) and a for a in spec["accepted_answers"]))
                self.assertIsInstance(spec["case_sensitive"], bool)

    def test_code_contract(self) -> None:
        for exercise in self.of_type(ResponseType.CODE):
            spec = exercise["evaluation_spec"]
            with self.subTest(exercise=exercise["slug"]):
                self.assertEqual(exercise["content"]["language"], "python")
                self.assertIsInstance(exercise["content"]["starter_code"], str)
                self.assertIn(spec["strategy"], {"stdout", "function"})
                self.assertTrue(spec["tests"])
                self.assertTrue(spec["reference_solution"].strip())
                if spec["strategy"] == "stdout":
                    for test in spec["tests"]:
                        self.assertEqual(set(test), {"stdin", "expected_stdout"})
                else:
                    self.assertTrue(spec["function_name"].isidentifier())
                    self.assertIn(f"def {spec['function_name']}(", spec["reference_solution"])
                    for test in spec["tests"]:
                        self.assertEqual(set(test), {"args", "kwargs", "expected"})
                        self.assertIsInstance(test["args"], list)
                        self.assertIsInstance(test["kwargs"], dict)
                    if exercise["learning_mode"] in {LearningMode.FIX, LearningMode.CREATE}:
                        self.assertGreaterEqual(len(spec["tests"]), 3)

    def test_text_contract(self) -> None:
        for exercise in self.of_type(ResponseType.TEXT):
            with self.subTest(exercise=exercise["slug"]):
                self.assertEqual(exercise["evaluation_spec"]["strategy"], "rubric")
                self.assertTrue(exercise["evaluation_spec"]["criteria"])

    def test_answers_never_sit_in_content(self) -> None:
        for exercise in EXERCISES:
            spec = exercise["evaluation_spec"]
            content_text = json.dumps(exercise["content"])
            with self.subTest(exercise=exercise["slug"]):
                self.assertNotIn("reference_solution", content_text)
                if "reference_solution" in spec:
                    self.assertNotEqual(
                        exercise["content"]["starter_code"], spec["reference_solution"]
                    )
                for test in spec.get("tests", []):
                    expected = test.get("expected_stdout")
                    if expected and len(expected) > 3:
                        self.assertNotIn(json.dumps(expected)[1:-1], content_text)

    @staticmethod
    def of_type(response_type: str) -> list[dict]:
        return [e for e in EXERCISES if e["response_type"] == response_type]


class SeedRequirementsTests(TestCase):
    def test_requires_the_curriculum(self) -> None:
        with self.assertRaisesMessage(CommandError, "seed_curriculum"):
            seed("seed_python_exercises")
        self.assertFalse(Exercise.objects.exists())


class SeededPackTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        seed("seed_curriculum")
        cls.output = seed("seed_python_exercises")

    def test_output_reports_creation(self) -> None:
        self.assertIn(f"Exercises: {len(EXERCISES)} created, 0 updated", self.output)

    def test_total_is_meaningful(self) -> None:
        self.assertEqual(Exercise.objects.count(), len(EXERCISES))
        self.assertTrue(120 <= Exercise.objects.count() <= 150)

    def test_every_skill_is_covered_with_all_four_modes(self) -> None:
        self.assertEqual(Skill.objects.count(), 11)
        for skill in Skill.objects.all():
            with self.subTest(skill=skill.slug):
                modes = set(
                    Exercise.objects.filter(lesson__concept__skill=skill).values_list(
                        "learning_mode", flat=True
                    )
                )
                self.assertEqual(modes, ALL_MODES)

    def test_every_concept_has_at_least_two_published_exercises(self) -> None:
        self.assertEqual(Concept.objects.count(), 53)
        published = Counter(
            published_exercises().values_list("lesson__concept__slug", "lesson__concept__skill")
        )
        for concept in Concept.objects.all():
            with self.subTest(concept=concept.slug):
                self.assertGreaterEqual(published[(concept.slug, concept.skill_id)], 2)

    def test_key_concepts_have_strong_coverage(self) -> None:
        for slug in KEY_CONCEPTS:
            exercises = Exercise.objects.filter(lesson__concept__slug=slug)
            with self.subTest(concept=slug):
                self.assertGreaterEqual(exercises.count(), 4)
                self.assertEqual(set(exercises.values_list("learning_mode", flat=True)), ALL_MODES)

    def test_every_exercise_is_valid_published_and_safe_to_present(self) -> None:
        for exercise in Exercise.objects.select_related("lesson"):
            with self.subTest(exercise=exercise.slug):
                exercise.full_clean()
                self.assertTrue(exercise.is_published)
                data = exercise_presentation(exercise)
                self.assertNotIn("evaluation_spec", data)
                serialized = json.dumps(data)
                for private_key in exercise.evaluation_spec:
                    self.assertNotIn(f'"{private_key}"', serialized)
                if "reference_solution" in exercise.evaluation_spec:
                    self.assertNotIn(
                        json.dumps(exercise.evaluation_spec["reference_solution"]), serialized
                    )
        self.assertEqual(published_exercises().count(), Exercise.objects.count())

    def test_production_pack_uses_only_python_response_types(self) -> None:
        used = set(Exercise.objects.values_list("response_type", flat=True))
        self.assertTrue(used <= PYTHON_RESPONSE_TYPES)
        self.assertTrue(
            {ResponseType.CODE, ResponseType.MULTIPLE_CHOICE, ResponseType.FILL_GAP} <= used
        )

    def test_second_run_creates_nothing(self) -> None:
        before = Exercise.objects.count()
        output = seed("seed_python_exercises")
        self.assertIn(f"Exercises: 0 created, {len(EXERCISES)} updated", output)
        self.assertEqual(Exercise.objects.count(), before)

    def test_unrelated_exercises_survive(self) -> None:
        lesson = Exercise.objects.get(slug="range-three").lesson
        manual = make_exercise(lesson, slug="teacher-extra", order=99, title="Teacher extra")
        seed("seed_python_exercises")
        manual.refresh_from_db()
        self.assertEqual(manual.title, "Teacher extra")
        self.assertEqual(Exercise.objects.count(), len(EXERCISES) + 1)

    def test_drift_is_repaired(self) -> None:
        exercise = Exercise.objects.get(slug="greater-than-ten")
        original = {
            field: getattr(exercise, field)
            for field in ("title", "prompt", "order", "content", "evaluation_spec")
        }
        Exercise.objects.filter(pk=exercise.pk).update(
            title="Edited",
            prompt="Edited prompt",
            order=50,
            content={"language": "python", "starter_code": "pass\n"},
            evaluation_spec={},
            is_published=False,
            target_seconds=None,
        )
        seed("seed_python_exercises")
        exercise.refresh_from_db()
        for field, value in original.items():
            self.assertEqual(getattr(exercise, field), value)
        self.assertTrue(exercise.is_published)
        self.assertIsNotNone(exercise.target_seconds)

    def test_reordered_lesson_is_repaired(self) -> None:
        lesson = Exercise.objects.get(slug="range-three").lesson
        first, second = lesson.exercises.order_by("order")
        Exercise.objects.filter(pk=first.pk).update(order=10)
        Exercise.objects.filter(pk=second.pk).update(order=1)
        Exercise.objects.filter(pk=first.pk).update(order=2)
        seed("seed_python_exercises")
        self.assertEqual(
            list(lesson.exercises.order_by("order").values_list("pk", flat=True)),
            [first.pk, second.pk],
        )

    def test_admin_shows_seeded_exercises(self) -> None:
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)
        response = self.client.get(
            reverse("admin:exercises_exercise_changelist"), {"q": "greater-than-ten"}
        )
        self.assertEqual(response.context["cl"].result_count, 1)
        exercise = Exercise.objects.get(slug="greater-than-ten")
        response = self.client.get(reverse("admin:exercises_exercise_change", args=[exercise.pk]))
        self.assertContains(response, "Only the big numbers")
        self.assertContains(response, "reference_solution")
