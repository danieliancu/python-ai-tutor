from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.curriculum.models import SkillPrerequisite


class CurriculumAdminTests(TestCase):
    model_names = [
        "world",
        "skill",
        "skillprerequisite",
        "concept",
        "conceptprerequisite",
        "lesson",
    ]

    @classmethod
    def setUpTestData(cls) -> None:
        call_command("seed_curriculum", stdout=StringIO())
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "pass-12345")

    def setUp(self) -> None:
        self.client.force_login(self.admin)

    def test_changelist_and_add_pages_render(self) -> None:
        for name in self.model_names:
            for view in ("changelist", "add"):
                with self.subTest(model=name, view=view):
                    response = self.client.get(reverse(f"admin:curriculum_{name}_{view}"))
                    self.assertEqual(response.status_code, 200)

    def test_change_pages_render_with_prerequisite_inlines(self) -> None:
        edge = SkillPrerequisite.objects.select_related("skill").first()
        response = self.client.get(reverse("admin:curriculum_skill_change", args=[edge.skill_id]))
        self.assertContains(response, "Prerequisites")
        response = self.client.get(
            reverse("admin:curriculum_skillprerequisite_change", args=[edge.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_search_and_filter(self) -> None:
        url = reverse("admin:curriculum_concept_changelist")
        response = self.client.get(url, {"q": "range"})
        self.assertContains(response, "range()")
        self.assertNotContains(response, "Tracebacks")

        response = self.client.get(
            reverse("admin:curriculum_lesson_changelist"), {"kind__exact": "challenge"}
        )
        self.assertContains(response, "Build your project")
        self.assertNotContains(response, "Your first program")

    def test_admin_form_rejects_a_cycle(self) -> None:
        edge = SkillPrerequisite.objects.select_related("skill", "prerequisite").get(
            skill__slug="variables"
        )
        response = self.client.post(
            reverse("admin:curriculum_skillprerequisite_add"),
            {"skill": edge.prerequisite_id, "prerequisite": edge.skill_id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "would create a cycle")
