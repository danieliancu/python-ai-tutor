from django.test import TestCase

from apps.curriculum.selectors import published_curriculum
from apps.curriculum.tests.helpers import make_concept, make_lesson, make_skill, make_world


def flatten(worlds) -> list:
    """Walk the tree the way templates will: world → skills → concepts → lessons."""
    return [
        (
            world.slug,
            [
                (
                    skill.slug,
                    [
                        (concept.slug, [lesson.slug for lesson in concept.lessons.all()])
                        for concept in skill.concepts.all()
                    ],
                )
                for skill in world.skills.all()
            ],
        )
        for world in worlds
    ]


class PublishedCurriculumTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        # Created out of order to prove ordering comes from `order`, not insertion.
        cls.second_world = make_world(slug="second", order=2)
        cls.first_world = make_world(slug="first", order=1)
        make_world(slug="draft-world", order=3, is_published=False)

        loops = make_skill(cls.first_world, slug="loops", order=2)
        basics = make_skill(cls.first_world, slug="basics", order=1)
        make_skill(cls.first_world, slug="draft-skill", order=3, is_published=False)
        make_skill(cls.second_world, slug="other", order=1)

        range_ = make_concept(loops, slug="range", order=2)
        for_loops = make_concept(loops, slug="for-loops", order=1)
        make_concept(loops, slug="draft-concept", order=3, is_published=False)
        values = make_concept(basics, slug="values", order=1)

        make_lesson(range_, slug="range-practice", order=2)
        make_lesson(range_, slug="range-intro", order=1)
        make_lesson(range_, slug="draft-lesson", order=3, is_published=False)
        make_lesson(for_loops, slug="for-intro", order=1)
        make_lesson(values, slug="values-intro", order=1)

        # Published children of an unpublished parent must stay hidden too.
        hidden_skill = make_skill(cls.first_world, slug="hidden", order=4, is_published=False)
        make_lesson(make_concept(hidden_skill, slug="under-hidden"), slug="under-hidden")

    def test_returns_only_published_tree_in_order(self) -> None:
        self.assertEqual(
            flatten(published_curriculum()),
            [
                (
                    "first",
                    [
                        ("basics", [("values", ["values-intro"])]),
                        (
                            "loops",
                            [
                                ("for-loops", ["for-intro"]),
                                ("range", ["range-intro", "range-practice"]),
                            ],
                        ),
                    ],
                ),
                ("second", [("other", [])]),
            ],
        )

    def test_traversal_uses_one_query_per_level(self) -> None:
        # Worlds, skills, concepts and lessons: four queries however large the tree is.
        with self.assertNumQueries(4):
            tree = flatten(published_curriculum())
        self.assertEqual(len(tree), 2)

    def test_query_count_does_not_grow_with_the_tree(self) -> None:
        for n in range(5):
            skill = make_skill(self.second_world, slug=f"bulk-{n}", order=10 + n)
            for m in range(3):
                make_lesson(make_concept(skill, slug=f"c-{m}"), slug=f"l-{m}")
        with self.assertNumQueries(4):
            flatten(published_curriculum())
