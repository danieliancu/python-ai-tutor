from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.curriculum.models import (
    Concept,
    ConceptPrerequisite,
    Lesson,
    Skill,
    SkillPrerequisite,
    World,
)
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill, make_world


class HierarchyTests(TestCase):
    def setUp(self) -> None:
        self.world = make_world("Python Foundations", slug="python-foundations")
        self.skill = make_skill(self.world, "Loops", slug="loops")
        self.concept = make_concept(self.skill, "range()", slug="range")
        self.lesson = make_lesson(self.concept, "Counting with range()", slug="counting")

    def test_relationships(self) -> None:
        self.assertEqual(list(self.world.skills.all()), [self.skill])
        self.assertEqual(list(self.skill.concepts.all()), [self.concept])
        self.assertEqual(list(self.concept.lessons.all()), [self.lesson])
        self.assertEqual(self.lesson.concept.skill.world, self.world)

    def test_lesson_defaults(self) -> None:
        self.assertEqual(self.lesson.kind, Lesson.Kind.LEARN)
        self.assertEqual(self.lesson.summary, "")

    def test_str(self) -> None:
        self.assertEqual(str(self.world), "Python Foundations")
        self.assertEqual(str(self.skill), "Python Foundations › Loops")
        self.assertEqual(str(self.concept), "Loops: range()")
        self.assertEqual(str(self.lesson), "range(): Counting with range()")

    def test_default_ordering_is_by_order_then_id(self) -> None:
        third = make_skill(self.world, "Third", order=3)
        second = make_skill(self.world, "Second", order=2)
        self.assertEqual(list(self.world.skills.all()), [self.skill, second, third])

        later = make_lesson(self.concept, "Later", order=5)
        earlier = make_lesson(self.concept, "Earlier", order=2)
        self.assertEqual(list(self.concept.lessons.all()), [self.lesson, earlier, later])

        late_world = make_world("Late", order=50)
        early_world = make_world("Early", order=2)
        self.assertEqual(list(World.objects.filter(order__lte=50)), [early_world, late_world])

    def test_same_slug_allowed_under_different_parents(self) -> None:
        other_world = make_world()
        other_skill = make_skill(other_world, slug="loops")
        other_concept = make_concept(other_skill, slug="range")
        make_lesson(other_concept, slug="counting")
        make_concept(self.skill, slug="range-2")
        self.assertEqual(Skill.objects.filter(slug="loops").count(), 2)


class ConstraintTests(TestCase):
    def setUp(self) -> None:
        self.world = make_world(order=1, slug="world")
        self.skill = make_skill(self.world, order=1, slug="skill")
        self.concept = make_concept(self.skill, order=1, slug="concept")
        make_lesson(self.concept, order=1, slug="lesson")

    def assert_integrity_error(self, model, **fields) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            model.objects.create(**fields)

    def test_world_slug_and_order_unique(self) -> None:
        base = {"title": "W", "description": "d"}
        self.assert_integrity_error(World, slug="world", order=2, **base)
        self.assert_integrity_error(World, slug="other", order=1, **base)

    def test_skill_slug_and_order_unique_within_world(self) -> None:
        base = {"world": self.world, "title": "S", "description": "d"}
        self.assert_integrity_error(Skill, slug="skill", order=2, **base)
        self.assert_integrity_error(Skill, slug="other", order=1, **base)

    def test_concept_slug_and_order_unique_within_skill(self) -> None:
        base = {"skill": self.skill, "title": "C", "description": "d", "learning_objective": "o"}
        self.assert_integrity_error(Concept, slug="concept", order=2, **base)
        self.assert_integrity_error(Concept, slug="other", order=1, **base)

    def test_lesson_slug_and_order_unique_within_concept(self) -> None:
        base = {"concept": self.concept, "title": "L", "objective": "o", "estimated_minutes": 5}
        self.assert_integrity_error(Lesson, slug="lesson", order=2, **base)
        self.assert_integrity_error(Lesson, slug="other", order=1, **base)

    def test_order_must_be_positive(self) -> None:
        self.assert_integrity_error(World, title="W", slug="w0", description="d", order=0)
        self.assert_integrity_error(
            Skill, world=self.world, title="S", slug="s0", description="d", order=0
        )
        self.assert_integrity_error(
            Concept,
            skill=self.skill,
            title="C",
            slug="c0",
            description="d",
            learning_objective="o",
            order=0,
        )
        self.assert_integrity_error(
            Lesson,
            concept=self.concept,
            title="L",
            slug="l0",
            objective="o",
            estimated_minutes=5,
            order=0,
        )

    def test_estimated_minutes_must_be_positive(self) -> None:
        self.assert_integrity_error(
            Lesson,
            concept=self.concept,
            title="L",
            slug="l2",
            objective="o",
            estimated_minutes=0,
            order=2,
        )

    def test_full_clean_reports_positive_value_errors(self) -> None:
        lesson = Lesson(
            concept=self.concept,
            title="L",
            slug="l3",
            objective="o",
            estimated_minutes=0,
            order=0,
        )
        with self.assertRaises(ValidationError) as ctx:
            lesson.full_clean()
        self.assertIn("order", ctx.exception.message_dict)
        self.assertIn("estimated_minutes", ctx.exception.message_dict)


class DeletionTests(TestCase):
    def setUp(self) -> None:
        self.world = make_world()
        self.first = make_skill(self.world)
        self.second = make_skill(self.world)
        self.third = make_skill(self.world)
        SkillPrerequisite.objects.create(skill=self.second, prerequisite=self.first)
        SkillPrerequisite.objects.create(skill=self.third, prerequisite=self.second)
        self.a = make_concept(self.first)
        self.b = make_concept(self.second)
        self.c = make_concept(self.third)
        ConceptPrerequisite.objects.create(concept=self.b, prerequisite=self.a)
        ConceptPrerequisite.objects.create(concept=self.c, prerequisite=self.b)
        make_lesson(self.a)
        make_lesson(self.b)

    def test_deleting_world_cascades_through_hierarchy_and_edges(self) -> None:
        self.world.delete()
        for model in (Skill, Concept, Lesson, SkillPrerequisite, ConceptPrerequisite):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.exists())

    def test_deleting_skill_removes_edges_in_both_directions(self) -> None:
        self.second.delete()
        self.assertFalse(SkillPrerequisite.objects.exists())
        # Its concept (b) is gone, and with it both concept edges that touched b.
        self.assertFalse(ConceptPrerequisite.objects.exists())
        self.assertEqual(Skill.objects.count(), 2)

    def test_deleting_concept_removes_its_edges_and_lessons(self) -> None:
        self.b.delete()
        self.assertFalse(ConceptPrerequisite.objects.exists())
        self.assertEqual(Lesson.objects.count(), 1)
        self.assertEqual(SkillPrerequisite.objects.count(), 2)
