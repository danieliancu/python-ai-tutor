from pathlib import Path

from django.test import TestCase

from apps.ai_tutor.adapters import FALLBACK, GenericTutorAdapter, adapter_for
from apps.ai_tutor.models import TutorTurn
from apps.ai_tutor.tests.helpers import TutorFixtures

GENERIC_MODULES = (
    "adapters.py",
    "assistance.py",
    "config.py",
    "constants.py",
    "context.py",
    "models.py",
    "pedagogy.py",
    "presentation.py",
    "prompts.py",
    "selectors.py",
    "services.py",
    "types.py",
    "views.py",
    "providers/base.py",
    "providers/openai.py",
    "providers/fake.py",
)


class DomainNeutralTutorTests(TutorFixtures, TestCase):
    def test_one_path_for_every_subject(self) -> None:
        cases = [
            (self.enrollment, self.mcq, self.python_world),
            (self.english_enrollment, self.translation, self.english_world),
            (self.maths_enrollment, self.numeric, self.maths_world),
        ]
        for enrollment, exercise, world in cases:
            with self.subTest(world=world.title):
                outcome = self.tutor("hint", exercise=exercise, enrollment=enrollment)
                self.assertEqual(outcome.turn.response_kind, "hint")
                request = self.last_request()
                self.assertEqual(request.server_context["world"]["id"], world.pk)
                self.assertEqual(
                    request.server_context["exercise"]["response_type"], exercise.response_type
                )
                self.assertNotIn("Domain guidance", request.instructions)
                self.assertNotIn("private_teaching", request.server_context)
                self.assertIs(adapter_for(world), FALLBACK)
        self.assertEqual(TutorTurn.objects.filter(status="complete").count(), 3)

    def test_generic_adapter_is_neutral(self) -> None:
        adapter = GenericTutorAdapter()
        self.assertEqual(adapter.extra_instructions({}), "")
        self.assertEqual(
            adapter.private_teaching_context(enrollment=None, exercise=None, latest_attempt=None),
            {},
        )
        self.assertEqual(adapter.postprocess_reply("  hi  "), "hi")

    def test_generic_modules_have_no_subject_logic(self) -> None:
        package = Path(__file__).resolve().parent.parent
        for name in GENERIC_MODULES:
            source = (package / name).read_text(encoding="utf-8").lower()
            with self.subTest(file=name):
                for word in ("python", "english", "maths", "slug ==", "romanian"):
                    self.assertNotIn(word, source)
