from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.validation import validate_exercise_json


def options(*items) -> dict:
    return {"options": list(items)}


A = {"id": "a", "text": "for"}
B = {"id": "b", "text": "while"}


class ChoicesTests(SimpleTestCase):
    def test_response_types_have_stable_values(self) -> None:
        self.assertEqual(
            ResponseType.values,
            [
                "code",
                "multiple_choice",
                "fill_gap",
                "text",
                "translation",
                "numeric",
                "math_expression",
                "speaking",
                "listening",
            ],
        )

    def test_learning_modes_have_stable_values(self) -> None:
        self.assertEqual(LearningMode.values, ["recognise", "complete", "fix", "create"])


EMPTY = object()


class ValidationTests(SimpleTestCase):
    def assert_valid(self, response_type: str, content, spec=EMPTY) -> None:
        validate_exercise_json(response_type, content, {} if spec is EMPTY else spec)

    def assert_invalid(self, response_type: str, content, spec=EMPTY, *, field="content", text=""):
        with self.assertRaises(ValidationError) as ctx:
            validate_exercise_json(response_type, content, {} if spec is EMPTY else spec)
        errors = ctx.exception.message_dict
        self.assertIn(field, errors)
        if text:
            self.assertIn(text, " ".join(errors[field]))

    def test_content_and_spec_must_be_objects(self) -> None:
        for bad in ([], "text", 3, None):
            with self.subTest(value=bad):
                self.assert_invalid(ResponseType.TEXT, bad, text="JSON object")
                self.assert_invalid(
                    ResponseType.TEXT, {}, bad, field="evaluation_spec", text="JSON object"
                )

    def test_types_without_a_shape_accept_empty_content(self) -> None:
        for response_type in (
            ResponseType.CODE,
            ResponseType.FILL_GAP,
            ResponseType.TEXT,
            ResponseType.TRANSLATION,
            ResponseType.NUMERIC,
            ResponseType.MATH_EXPRESSION,
            ResponseType.SPEAKING,
            ResponseType.LISTENING,
        ):
            with self.subTest(response_type=response_type):
                self.assert_valid(response_type, {})

    def test_code_content(self) -> None:
        self.assert_valid(ResponseType.CODE, {"language": "python", "starter_code": "x = 1\n"})
        self.assert_invalid(ResponseType.CODE, {"language": 3}, text="language")
        self.assert_invalid(ResponseType.CODE, {"starter_code": ["x"]}, text="starter_code")

    def test_fill_gap_and_translation_content(self) -> None:
        self.assert_valid(ResponseType.FILL_GAP, {"template": "if age __ 18:"})
        self.assert_invalid(ResponseType.FILL_GAP, {"template": None}, text="template")
        self.assert_valid(
            ResponseType.TRANSLATION,
            {"source_language": "ro", "target_language": "en-GB", "source_text": "Salut"},
        )
        for key in ("source_language", "target_language", "source_text"):
            with self.subTest(key=key):
                self.assert_invalid(ResponseType.TRANSLATION, {key: 1}, text=key)

    def test_valid_multiple_choice(self) -> None:
        self.assert_valid(ResponseType.MULTIPLE_CHOICE, options(A, B, {"id": "c", "text": "do"}))

    def test_multiple_choice_needs_an_options_list(self) -> None:
        self.assert_invalid(ResponseType.MULTIPLE_CHOICE, {}, text="options")
        self.assert_invalid(ResponseType.MULTIPLE_CHOICE, {"options": "a,b"}, text="options")
        self.assert_invalid(ResponseType.MULTIPLE_CHOICE, options(A), text="at least two")

    def test_malformed_options_are_rejected(self) -> None:
        for bad in (
            "just text",
            {"id": "b"},
            {"text": "no id"},
            {"id": "", "text": "blank id"},
            {"id": 2, "text": "numeric id"},
            {"id": "b", "text": "   "},
        ):
            with self.subTest(option=bad):
                self.assert_invalid(ResponseType.MULTIPLE_CHOICE, options(A, bad), text="Option 2")

    def test_duplicate_option_ids_are_rejected(self) -> None:
        self.assert_invalid(
            ResponseType.MULTIPLE_CHOICE,
            options(A, {"id": "a", "text": "again"}),
            text="more than once",
        )

    def test_options_must_not_reveal_the_answer(self) -> None:
        for marker in ("correct", "is_correct", "answer"):
            with self.subTest(marker=marker):
                self.assert_invalid(
                    ResponseType.MULTIPLE_CHOICE,
                    options({**A, marker: True}, B),
                    text="evaluation_spec",
                )

    def test_content_must_not_carry_answers_for_any_type(self) -> None:
        for response_type in ResponseType.values:
            for key in ("answer", "correct_option", "solution", "accepted_answers"):
                with self.subTest(response_type=response_type, key=key):
                    content = {"x": 1, key: "secret"}
                    if response_type == ResponseType.MULTIPLE_CHOICE:
                        content.update(options(A, B))
                    self.assert_invalid(response_type, content, text=key)

    def test_answers_belong_in_the_evaluation_spec(self) -> None:
        self.assert_valid(
            ResponseType.MULTIPLE_CHOICE,
            options(A, B),
            {"correct_option": "a", "explanation": "for iterates over a sequence."},
        )

    def test_errors_for_both_payloads_are_reported_together(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_exercise_json(ResponseType.MULTIPLE_CHOICE, {}, [])
        self.assertEqual(set(ctx.exception.message_dict), {"content", "evaluation_spec"})
