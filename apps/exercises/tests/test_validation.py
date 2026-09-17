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


STDOUT_TEST = {"stdin": "", "expected_stdout": "hi\n"}
FUNCTION_TEST = {"args": [2], "kwargs": {}, "expected": 4}
VALID_SPECS = {
    ResponseType.MULTIPLE_CHOICE: ({"options": [A, B]}, {"correct_option": "b"}),
    ResponseType.FILL_GAP: ({"template": "x __ 1"}, {"accepted_answers": [">"]}),
    ResponseType.NUMERIC: ({}, {"expected": 12.5, "tolerance": 0}),
    ResponseType.TEXT: ({}, {"strategy": "rubric", "criteria": ["Clear steps."]}),
    ResponseType.CODE: ({}, {"strategy": "stdout", "tests": [STDOUT_TEST]}),
}


class EvaluationSpecTests(SimpleTestCase):
    def assert_spec_valid(self, response_type, spec, content=None) -> None:
        content = VALID_SPECS[response_type][0] if content is None else content
        validate_exercise_json(response_type, content, spec, require_spec=True)

    def assert_spec_invalid(self, response_type, spec, text="", content=None) -> None:
        content = VALID_SPECS[response_type][0] if content is None else content
        with self.assertRaises(ValidationError) as ctx:
            validate_exercise_json(response_type, content, spec, require_spec=True)
        self.assertIn("evaluation_spec", ctx.exception.message_dict)
        if text:
            self.assertIn(text, " ".join(ctx.exception.message_dict["evaluation_spec"]))

    def test_valid_specs(self) -> None:
        for response_type, (content, spec) in VALID_SPECS.items():
            with self.subTest(response_type=response_type):
                self.assert_spec_valid(response_type, spec, content)

    def test_empty_spec_is_only_allowed_for_drafts(self) -> None:
        for response_type, (content, _) in VALID_SPECS.items():
            with self.subTest(response_type=response_type):
                validate_exercise_json(response_type, content, {}, require_spec=False)
                self.assert_spec_invalid(response_type, {}, content=content)

    def test_non_empty_specs_are_checked_even_for_drafts(self) -> None:
        with self.assertRaises(ValidationError):
            validate_exercise_json(
                ResponseType.NUMERIC, {}, {"expected": "twelve"}, require_spec=False
            )

    def test_types_without_a_contract_accept_any_object(self) -> None:
        for response_type in (
            ResponseType.TRANSLATION,
            ResponseType.MATH_EXPRESSION,
            ResponseType.SPEAKING,
            ResponseType.LISTENING,
        ):
            with self.subTest(response_type=response_type):
                validate_exercise_json(response_type, {}, {}, require_spec=True)
                validate_exercise_json(response_type, {}, {"anything": [1]}, require_spec=True)

    def test_multiple_choice_spec(self) -> None:
        for spec in ({}, {"correct_option": ""}, {"correct_option": 1}):
            with self.subTest(spec=spec):
                self.assert_spec_invalid(ResponseType.MULTIPLE_CHOICE, spec, "correct_option")
        self.assert_spec_invalid(
            ResponseType.MULTIPLE_CHOICE, {"correct_option": "z"}, "not one of the option ids"
        )

    def test_fill_gap_spec(self) -> None:
        for spec in (
            {"accepted_answers": []},
            {"accepted_answers": ">"},
            {"accepted_answers": [""]},
            {"accepted_answers": [">", 1]},
        ):
            with self.subTest(spec=spec):
                self.assert_spec_invalid(ResponseType.FILL_GAP, spec, "accepted_answers")
        self.assert_spec_invalid(
            ResponseType.FILL_GAP,
            {"accepted_answers": [">"], "case_sensitive": "no"},
            "case_sensitive",
        )
        self.assert_spec_valid(
            ResponseType.FILL_GAP, {"accepted_answers": ["x"], "case_sensitive": False}
        )

    def test_numeric_spec(self) -> None:
        for spec in (
            {"expected": "12"},
            {"expected": True},
            {"expected": float("nan")},
            {"expected": float("inf")},
        ):
            with self.subTest(spec=spec):
                self.assert_spec_invalid(ResponseType.NUMERIC, spec, "expected")
        for tolerance in (-1, "0.1", float("inf"), True):
            with self.subTest(tolerance=tolerance):
                self.assert_spec_invalid(
                    ResponseType.NUMERIC, {"expected": 1, "tolerance": tolerance}, "tolerance"
                )
        self.assert_spec_valid(ResponseType.NUMERIC, {"expected": -3})

    def test_text_spec(self) -> None:
        self.assert_spec_invalid(ResponseType.TEXT, {"criteria": ["x"]}, "rubric")
        for criteria in ([], [""], "x", None):
            with self.subTest(criteria=criteria):
                self.assert_spec_invalid(
                    ResponseType.TEXT, {"strategy": "rubric", "criteria": criteria}, "criteria"
                )

    def test_code_spec(self) -> None:
        function_spec = {
            "strategy": "function",
            "function_name": "double",
            "tests": [FUNCTION_TEST],
            "reference_solution": "def double(n):\n    return n * 2\n",
        }
        self.assert_spec_valid(ResponseType.CODE, function_spec)
        for spec, text in (
            ({"strategy": "shell", "tests": [STDOUT_TEST]}, "strategy"),
            ({"strategy": "stdout", "tests": []}, "tests"),
            ({"strategy": "stdout"}, "tests"),
            ({"strategy": "stdout", "tests": [{"stdin": ""}]}, "expected_stdout"),
            ({"strategy": "stdout", "tests": ["x"]}, "must be an object"),
            ({**function_spec, "function_name": "not valid"}, "function_name"),
            ({**function_spec, "function_name": None}, "function_name"),
            ({**function_spec, "tests": [{"args": 2, "kwargs": {}, "expected": 4}]}, "args"),
            ({**function_spec, "tests": [{"args": [2], "kwargs": {}}]}, "expected"),
            ({**function_spec, "reference_solution": 5}, "reference_solution"),
        ):
            with self.subTest(spec=spec):
                self.assert_spec_invalid(ResponseType.CODE, spec, text)


class MisconceptionTagTests(SimpleTestCase):
    content = {"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]}

    def spec(self, tags) -> dict:
        return {"correct_option": "a", "misconceptions": tags}

    def test_valid_tags_are_accepted_for_any_type(self) -> None:
        validate_exercise_json(
            ResponseType.MULTIPLE_CHOICE, self.content, self.spec(["off-by-one", "sign_error"])
        )
        validate_exercise_json(ResponseType.MULTIPLE_CHOICE, self.content, self.spec([]))
        validate_exercise_json(ResponseType.SPEAKING, {}, {"misconceptions": ["third-person-s"]})

    def test_malformed_tags_are_rejected(self) -> None:
        for tags in (
            "off-by-one",
            ["Off-By-One"],
            ["off by one"],
            ["-leading"],
            ["off-by-one", "off-by-one"],
            [3],
            ["x" * 65],
        ):
            with self.subTest(tags=tags), self.assertRaises(ValidationError) as caught:
                validate_exercise_json(ResponseType.MULTIPLE_CHOICE, self.content, self.spec(tags))
            self.assertIn("evaluation_spec", caught.exception.message_dict)
