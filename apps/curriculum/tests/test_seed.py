from collections import defaultdict
from io import StringIO

from django.core.management import call_command
from django.db.models import F
from django.test import TestCase

from apps.curriculum.models import (
    Concept,
    ConceptPrerequisite,
    Lesson,
    Skill,
    SkillPrerequisite,
    World,
)
from apps.curriculum.tests.helpers import make_skill

MODELS = (World, Skill, Concept, Lesson, SkillPrerequisite, ConceptPrerequisite)

EXPECTED_SKILLS = [
    ("start", "Start"),
    ("variables", "Variables"),
    ("decisions", "Decisions"),
    ("collections", "Collections"),
    ("loops", "Loops"),
    ("functions", "Functions"),
    ("debugging", "Debugging"),
    ("python-structure", "Python Structure"),
    ("oop-basics", "OOP Basics"),
    ("real-data", "Real Data"),
    ("python-developer", "Python Developer"),
]


def seed() -> str:
    out = StringIO()
    call_command("seed_curriculum", stdout=out)
    return out.getvalue()


def counts() -> dict[str, int]:
    return {model.__name__: model.objects.count() for model in MODELS}


def is_acyclic(edges: list[tuple[int, int]]) -> bool:
    """Kahn's algorithm over (node, prerequisite) pairs."""
    requires = defaultdict(set)
    required_by = defaultdict(set)
    nodes = set()
    for node, prerequisite in edges:
        requires[node].add(prerequisite)
        required_by[prerequisite].add(node)
        nodes |= {node, prerequisite}
    ready = [n for n in nodes if not requires[n]]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for dependent in required_by[current]:
            requires[dependent].discard(current)
            if not requires[dependent]:
                ready.append(dependent)
    return visited == len(nodes)


class SeedCurriculumTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.output = seed()
        cls.world = World.objects.get(slug="python-foundations")

    def concept(self, skill_slug: str, concept_slug: str) -> Concept:
        return Concept.objects.get(skill__slug=skill_slug, slug=concept_slug)

    def test_single_published_world(self) -> None:
        self.assertEqual(World.objects.count(), 1)
        self.assertEqual(self.world.title, "Python Foundations")
        self.assertTrue(self.world.is_published)

    def test_eleven_skills_in_order(self) -> None:
        skills = list(self.world.skills.values_list("slug", "title", "order"))
        expected = [(slug, title, i) for i, (slug, title) in enumerate(EXPECTED_SKILLS, 1)]
        self.assertEqual(skills, expected)

    def test_concepts_live_in_their_skills(self) -> None:
        expectations = {
            "start": ["running-python", "print-and-output", "comments", "expressions"],
            "decisions": [
                "booleans",
                "comparison-operators",
                "if-statements",
                "elif-and-else",
                "logical-operators",
            ],
            "collections": [
                "list-basics",
                "indexing-and-slicing",
                "list-mutation",
                "tuples",
                "dictionaries",
                "sets",
            ],
            "loops": ["for-loops", "range", "while-loops", "break-and-continue", "nested-loops"],
            "python-developer": [
                "project-planning",
                "build-and-integration",
                "testing-and-refactoring",
                "final-project",
            ],
        }
        for skill_slug, concept_slugs in expectations.items():
            with self.subTest(skill=skill_slug):
                actual = Concept.objects.filter(skill__slug=skill_slug).values_list(
                    "slug", flat=True
                )
                self.assertEqual(list(actual), concept_slugs)
        per_skill = {s.slug: s.concepts.count() for s in self.world.skills.all()}
        self.assertEqual(
            per_skill,
            {
                "start": 4,
                "variables": 5,
                "decisions": 5,
                "collections": 6,
                "loops": 5,
                "functions": 5,
                "debugging": 5,
                "python-structure": 4,
                "oop-basics": 5,
                "real-data": 5,
                "python-developer": 4,
            },
        )
        self.assertEqual(self.concept("oop-basics", "init-method").title, "__init__")
        self.assertEqual(self.concept("loops", "range").title, "range()")

    def test_every_concept_has_an_objective_and_a_lesson(self) -> None:
        for concept in Concept.objects.prefetch_related("lessons"):
            with self.subTest(concept=concept.slug):
                self.assertGreater(len(concept.learning_objective), 40)
                self.assertTrue(concept.lessons.all())
                self.assertTrue(concept.is_published)
        self.assertFalse(Concept.objects.filter(lessons__isnull=True).exists())

    def test_objectives_name_what_misconception_tracking_needs(self) -> None:
        comparison = self.concept("decisions", "comparison-operators").learning_objective
        for operator in ("<", ">", "<=", ">=", "==", "!="):
            self.assertIn(operator, comparison)
        range_objective = self.concept("loops", "range").learning_objective
        for word in ("start", "stop", "step", "exclusive"):
            self.assertIn(word, range_objective)

    def test_lessons_are_valid_and_varied(self) -> None:
        self.assertFalse(Lesson.objects.filter(is_published=False).exists())
        self.assertFalse(Lesson.objects.filter(objective="").exists())
        kinds = set(Lesson.objects.values_list("kind", flat=True))
        self.assertTrue({Lesson.Kind.LEARN, Lesson.Kind.PRACTICE} <= kinds)
        minutes = set(Lesson.objects.values_list("estimated_minutes", flat=True))
        self.assertGreater(len(minutes), 3)
        final = Lesson.objects.get(concept__slug="final-project", kind=Lesson.Kind.CHALLENGE)
        self.assertGreaterEqual(final.estimated_minutes, 30)

    def test_skill_prerequisites_form_the_learning_path(self) -> None:
        edges = set(SkillPrerequisite.objects.values_list("skill__slug", "prerequisite__slug"))
        slugs = [slug for slug, _ in EXPECTED_SKILLS]
        self.assertEqual(edges, set(zip(slugs[1:], slugs[:-1], strict=True)))

    def test_meaningful_concept_prerequisites(self) -> None:
        edges = set(ConceptPrerequisite.objects.values_list("concept__slug", "prerequisite__slug"))
        for edge in [
            ("if-statements", "booleans"),
            ("if-statements", "comparison-operators"),
            ("elif-and-else", "if-statements"),
            ("logical-operators", "booleans"),
            ("list-mutation", "list-basics"),
            ("indexing-and-slicing", "list-basics"),
            ("for-loops", "list-basics"),
            ("range", "for-loops"),
            ("nested-loops", "for-loops"),
            ("break-and-continue", "for-loops"),
            ("return-values", "defining-and-calling-functions"),
            ("parameters", "defining-and-calling-functions"),
            ("default-arguments", "parameters"),
            ("tracebacks", "runtime-errors"),
            ("debugging-workflow", "logic-errors"),
            ("modules", "imports"),
            ("packages", "modules"),
            ("attributes", "classes-and-objects"),
            ("methods", "classes-and-objects"),
            ("init-method", "classes-and-objects"),
            ("basic-inheritance", "classes-and-objects"),
            ("basic-inheritance", "methods"),
            ("files", "paths"),
            ("json", "files"),
            ("csv", "files"),
            ("final-project", "project-planning"),
            ("final-project", "build-and-integration"),
            ("final-project", "testing-and-refactoring"),
        ]:
            with self.subTest(edge=edge):
                self.assertIn(edge, edges)
        cross_skill = ConceptPrerequisite.objects.exclude(concept__skill=F("prerequisite__skill"))
        self.assertTrue(cross_skill.exists())

    def test_prerequisite_graphs_are_acyclic(self) -> None:
        skill_edges = list(SkillPrerequisite.objects.values_list("skill_id", "prerequisite_id"))
        concept_edges = list(
            ConceptPrerequisite.objects.values_list("concept_id", "prerequisite_id")
        )
        self.assertTrue(is_acyclic(skill_edges))
        self.assertTrue(is_acyclic(concept_edges))

    def test_output_reports_what_happened(self) -> None:
        self.assertIn("Skills: 11 created, 0 updated", self.output)
        self.assertIn("Seeded curriculum: Python Foundations", self.output)


class SeedIdempotencyTests(TestCase):
    def test_second_run_creates_nothing(self) -> None:
        seed()
        first = counts()
        output = seed()
        self.assertEqual(counts(), first)
        self.assertIn("Worlds: 0 created, 1 updated", output)
        self.assertIn("Lessons: 0 created", output)
        self.assertIn("Skill edges: 0 created, 10 already present", output)
        self.assertRegex(output, r"Concept edges: 0 created, \d+ already present")

    def test_reseed_repairs_drift_and_keeps_unrelated_records(self) -> None:
        seed()
        world = World.objects.get(slug="python-foundations")
        loops = world.skills.get(slug="loops")
        loops.title = "Edited"
        loops.save()
        extra = make_skill(world, "Extra skill", slug="extra", order=99)
        first = counts()

        seed()

        loops.refresh_from_db()
        self.assertEqual(loops.title, "Loops")
        self.assertEqual(loops.order, 5)
        self.assertTrue(Skill.objects.filter(pk=extra.pk, order=99).exists())
        self.assertEqual(counts(), first)

    def test_reseed_handles_reordered_records(self) -> None:
        seed()
        world = World.objects.get(slug="python-foundations")
        # Simulate an older definition where two skills had swapped positions.
        start = world.skills.get(slug="start")
        variables = world.skills.get(slug="variables")
        start.order = 50
        start.save()
        variables.order = 1
        variables.save()
        start.order = 2
        start.save()

        seed()

        self.assertEqual(
            list(world.skills.values_list("slug", flat=True)[:2]), ["start", "variables"]
        )
