from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.curriculum.models import Lesson, World
from apps.exercises.models import Exercise


class SeedCurriculumRegressionTests(TestCase):
    def test_seed_still_builds_the_curriculum_without_exercises(self) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        call_command("seed_curriculum", stdout=StringIO())
        self.assertEqual(list(World.objects.values_list("slug", flat=True)), ["python-foundations"])
        self.assertEqual(Lesson.objects.count(), 59)
        self.assertFalse(Exercise.objects.exists())
