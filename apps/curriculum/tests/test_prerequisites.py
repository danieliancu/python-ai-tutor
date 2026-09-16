from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.curriculum.models import ConceptPrerequisite, SkillPrerequisite
from apps.curriculum.tests.helpers import make_concept, make_skill, make_world


class PrerequisiteRules:
    """Rules shared by both edge models. Subclasses provide nodes and an edge factory."""

    edge_model: type
    node_field: str

    def make_node(self, title: str, world=None):
        raise NotImplementedError

    def require(self, node, prerequisite):
        return self.edge_model.objects.create(
            **{self.node_field: node, "prerequisite": prerequisite}
        )

    def assert_rejected(self, node, prerequisite, message: str) -> ValidationError:
        with self.assertRaises(ValidationError) as ctx:
            self.require(node, prerequisite)
        self.assertIn(message, " ".join(ctx.exception.messages))
        return ctx.exception

    def setUp(self) -> None:
        self.world = make_world()
        self.a = self.make_node("A")
        self.b = self.make_node("B")
        self.c = self.make_node("C")
        self.d = self.make_node("D")

    def test_valid_dependency_is_accepted(self) -> None:
        edge = self.require(self.b, self.a)
        self.assertEqual(self.edge_model.objects.get(), edge)
        self.assertEqual(str(edge), "B requires A")
        self.assertEqual(list(self.b.prerequisite_links.all()), [edge])
        self.assertEqual(list(self.a.required_by_links.all()), [edge])

    def test_self_dependency_is_rejected(self) -> None:
        self.assert_rejected(self.a, self.a, "cannot require itself")
        self.assertFalse(self.edge_model.objects.exists())

    def test_self_dependency_is_rejected_by_the_database(self) -> None:
        edge = self.edge_model(**{self.node_field: self.a, "prerequisite": self.a})
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.edge_model.objects.bulk_create([edge])

    def test_cross_world_dependency_is_rejected(self) -> None:
        stranger = self.make_node("Stranger", world=make_world())
        self.assert_rejected(self.a, stranger, "same World")

    def test_duplicate_edge_is_rejected(self) -> None:
        self.require(self.b, self.a)
        with self.assertRaises(ValidationError):
            self.require(self.b, self.a)
        self.assertEqual(self.edge_model.objects.count(), 1)

    def test_duplicate_edge_is_rejected_by_the_database(self) -> None:
        self.require(self.b, self.a)
        edge = self.edge_model(**{self.node_field: self.b, "prerequisite": self.a})
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.edge_model.objects.bulk_create([edge])

    def test_direct_cycle_is_rejected(self) -> None:
        self.require(self.b, self.a)
        self.assert_rejected(self.a, self.b, "would create a cycle: A → B → A")

    def test_multi_hop_cycle_is_rejected(self) -> None:
        self.require(self.b, self.a)  # B requires A
        self.require(self.c, self.b)  # C requires B
        self.assert_rejected(self.a, self.c, "would create a cycle: A → C → B → A")
        self.assertEqual(self.edge_model.objects.count(), 2)

    def test_longer_cycle_is_rejected(self) -> None:
        self.require(self.b, self.a)
        self.require(self.c, self.b)
        self.require(self.d, self.c)
        self.assert_rejected(self.a, self.d, "A → D → C → B → A")

    def test_diamond_is_not_a_cycle(self) -> None:
        self.require(self.b, self.a)
        self.require(self.c, self.a)
        self.require(self.d, self.b)
        self.require(self.d, self.c)
        self.assertEqual(self.edge_model.objects.count(), 4)

    def test_resaving_an_existing_edge_is_not_a_cycle(self) -> None:
        self.require(self.b, self.a)
        edge = self.require(self.c, self.b)
        edge.save()
        self.assertEqual(self.edge_model.objects.count(), 2)

    def test_redirecting_an_edge_into_a_cycle_is_rejected(self) -> None:
        self.require(self.b, self.a)
        edge = self.require(self.c, self.b)
        # Turning "C requires B" into "A requires B" closes the loop with "B requires A".
        setattr(edge, self.node_field, self.a)
        with self.assertRaises(ValidationError):
            edge.save()


class SkillPrerequisiteTests(PrerequisiteRules, TestCase):
    edge_model = SkillPrerequisite
    node_field = "skill"

    def make_node(self, title: str, world=None):
        return make_skill(world or self.world, title)


class ConceptPrerequisiteTests(PrerequisiteRules, TestCase):
    edge_model = ConceptPrerequisite
    node_field = "concept"

    def make_node(self, title: str, world=None):
        if world is not None:
            return make_concept(make_skill(world), title)
        # Alternate between two skills so the shared rules also run across skill boundaries.
        if not hasattr(self, "skills"):
            self.skills = [make_skill(self.world), make_skill(self.world)]
            self.nodes_made = 0
        self.nodes_made += 1
        return make_concept(self.skills[self.nodes_made % 2], title)

    def test_same_skill_dependency_is_accepted(self) -> None:
        skill = make_skill(self.world)
        first = make_concept(skill, "First")
        second = make_concept(skill, "Second")
        self.require(second, first)
        self.assertTrue(
            ConceptPrerequisite.objects.filter(concept=second, prerequisite=first).exists()
        )

    def test_cross_skill_same_world_dependency_is_accepted(self) -> None:
        early = make_concept(make_skill(self.world), "Early")
        late = make_concept(make_skill(self.world), "Late")
        self.assertNotEqual(early.skill_id, late.skill_id)
        self.require(late, early)
        self.assertEqual(late.prerequisite_links.get().prerequisite, early)
