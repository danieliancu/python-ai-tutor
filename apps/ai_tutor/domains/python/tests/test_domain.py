from importlib import import_module
from io import StringIO
from pathlib import Path

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import TestCase

from apps.ai_tutor.adapters import FALLBACK, GenericTutorAdapter, adapter_for
from apps.ai_tutor.domains.python.adapter import PythonTutorAdapter
from apps.curriculum.models import World
from apps.curriculum.tests.helpers import make_world

AI_TUTOR = Path(__file__).resolve().parents[3]


class WorldDomainTests(TestCase):
    def test_seeded_python_world(self) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        world = World.objects.get(slug="python-foundations")
        self.assertEqual(world.domain, "python")
        self.assertIsInstance(adapter_for(world), PythonTutorAdapter)

    def test_other_worlds_default_to_general(self) -> None:
        world = make_world("English A1")
        self.assertEqual(world.domain, "general")
        self.assertIs(adapter_for(world), FALLBACK)
        self.assertIsInstance(FALLBACK, GenericTutorAdapter)
        self.assertIs(adapter_for(make_world("Maths", domain="maths")), FALLBACK)

    def test_domain_decides_not_the_slug(self) -> None:
        renamed = make_world("Anything", slug="not-python-at-all", domain="python")
        self.assertIsInstance(adapter_for(renamed), PythonTutorAdapter)
        lookalike = make_world("Python Foundations copy", slug="python-foundations-copy")
        self.assertIs(adapter_for(lookalike), FALLBACK)

    def test_data_migration_marks_the_existing_python_world(self) -> None:
        migration = import_module("apps.curriculum.migrations.0002_world_domain")
        world = make_world("Python Foundations", slug="python-foundations", domain="general")
        other = make_world("Other")
        migration.set_python_domain(django_apps, None)
        world.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((world.domain, other.domain), ("python", "general"))

    def test_no_runtime_slug_dispatch(self) -> None:
        for path in AI_TUTOR.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("python-foundations", source)
                self.assertNotIn("slug ==", source)
