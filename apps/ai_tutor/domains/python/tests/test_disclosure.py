from django.test import SimpleTestCase, TestCase

from apps.ai_tutor.domains.python.disclosure import leaks_reference
from apps.ai_tutor.domains.python.tests.helpers import FUNCTION_REFERENCE, PythonTutorFixtures
from apps.ai_tutor.models import TutorExerciseState, TutorTurn
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.services import TutorRequestError


class LeakGuardTests(SimpleTestCase):
    def test_full_reference_is_detected(self) -> None:
        for reply in (
            f"Here you go:\n```python\n{FUNCTION_REFERENCE}```",
            f"Try this:\n\n{FUNCTION_REFERENCE}\nThat's it.",
            "```\ndef   count_up_to(n):\n\n        return list(range(1,  n + 1))   \n```",
            f"```python\n# fixed\n{FUNCTION_REFERENCE}print(count_up_to(3))\n```",
        ):
            with self.subTest(reply=reply[:30]):
                self.assertTrue(leaks_reference(reply, FUNCTION_REFERENCE))

    def test_partial_or_different_code_passes(self) -> None:
        for reply in (
            "Look at the stop value in `range(1, n)`: is it included?",
            "```python\nfor i in range(1, 4):\n    print(i)\n```",
            "```python\ndef count_up_to(n):\n    ...\n```",
            "The line `return list(range(1, n + 1))` would be one way.",
            "",
        ):
            with self.subTest(reply=reply[:30]):
                self.assertFalse(leaks_reference(reply, FUNCTION_REFERENCE))

    def test_trivial_references_are_ignored(self) -> None:
        self.assertFalse(leaks_reference("x = 1", "x = 1"))
        self.assertFalse(leaks_reference("anything", None))
        self.assertTrue(leaks_reference("print('Access granted')", "print('Access granted')\n"))


class DisclosureGuardServiceTests(PythonTutorFixtures, TestCase):
    def test_leaking_hint_is_rejected_and_never_stored(self) -> None:
        leaky = FakeTutorProvider(reply=f"```python\n{FUNCTION_REFERENCE}```")
        with self.assertRaises(TutorRequestError) as caught:
            self.tutor("hint", exercise=self.function, provider=leaky)
        self.assertEqual(
            (caught.exception.code, caught.exception.status), ("tutor_unavailable", 503)
        )
        turn = TutorTurn.objects.get()
        self.assertEqual((turn.status, turn.error_code), ("failed", "provider_invalid_response"))
        self.assertEqual(turn.assistant_message, "")
        state = TutorExerciseState.objects.get(exercise=self.function)
        self.assertEqual((state.hint_level, state.used_solution), (0, False))
        self.assertNotIn("range(1, n + 1)", str(TutorTurn.objects.values().get()))

    def test_leaking_explanation_is_rejected(self) -> None:
        self.tutor("hint", exercise=self.function)
        self.tutor("hint", exercise=self.function)
        leaky = FakeTutorProvider(reply=FUNCTION_REFERENCE)
        with self.assertRaises(TutorRequestError):
            self.tutor("explain", exercise=self.function, provider=leaky)
        state = TutorExerciseState.objects.get(exercise=self.function)
        self.assertFalse(state.used_explanation)

    def test_solution_may_show_the_reference(self) -> None:
        for _ in range(3):
            self.tutor("solution", exercise=self.function)
        full = FakeTutorProvider(reply=f"```python\n{FUNCTION_REFERENCE}```")
        outcome = self.tutor("solution", exercise=self.function, provider=full)
        self.assertEqual(outcome.turn.response_kind, "solution")
        self.assertIn("range(1, n + 1)", outcome.turn.assistant_message)
        self.assertTrue(outcome.assistance.used_solution)

    def test_generic_worlds_are_not_guarded(self) -> None:
        self.python_world.domain = "general"
        self.python_world.save()
        leaky = FakeTutorProvider(reply=FUNCTION_REFERENCE)
        outcome = self.tutor("hint", exercise=self.function, provider=leaky)
        self.assertEqual(outcome.turn.status, "complete")
