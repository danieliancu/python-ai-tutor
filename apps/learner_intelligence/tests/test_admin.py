from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learner_intelligence.services import refresh_concept_state
from apps.learner_intelligence.tests.helpers import IntelligenceFixtures


class LearnerIntelligenceAdminTests(IntelligenceFixtures, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.make_attempt(self.by_mode["fix"])
        self.state = refresh_concept_state(self.enrollment, self.concept)
        self.mode = self.state.mode_states.get()
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(admin)

    def test_pages_render(self) -> None:
        for url in (
            reverse("admin:learner_intelligence_conceptstate_changelist"),
            reverse("admin:learner_intelligence_conceptstate_change", args=[self.state.pk]),
            reverse("admin:learner_intelligence_conceptmodestate_changelist"),
            reverse("admin:learner_intelligence_conceptmodestate_change", args=[self.mode.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_filters_and_search(self) -> None:
        url = reverse("admin:learner_intelligence_conceptstate_changelist")
        for params, count in (
            ({"q": "learner"}, 1),
            ({"q": self.concept.title}, 1),
            ({"q": "nobody"}, 0),
            ({"mastery_band": "learning"}, 1),
            ({"mastery_band": "mastered"}, 0),
            ({"enrollment__world__id__exact": self.python_world.pk}, 1),
            ({"enrollment__world__id__exact": self.english_world.pk}, 0),
            ({"trend": "insufficient_data"}, 1),
        ):
            with self.subTest(params=params):
                response = self.client.get(url, params)
                self.assertEqual(response.context["cl"].result_count, count)

    def test_derived_state_cannot_be_added_or_edited(self) -> None:
        for name in ("conceptstate", "conceptmodestate"):
            with self.subTest(model=name):
                url = reverse(f"admin:learner_intelligence_{name}_add")
                self.assertEqual(self.client.get(url).status_code, 403)
        change = reverse("admin:learner_intelligence_conceptstate_change", args=[self.state.pk])
        response = self.client.post(change, {"mastery_score": "100"})
        self.assertEqual(response.status_code, 403)
        self.state.refresh_from_db()
        self.assertNotEqual(str(self.state.mastery_score), "100.00")
