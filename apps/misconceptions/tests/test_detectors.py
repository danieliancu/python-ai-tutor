from django.test import SimpleTestCase

from apps.attempts.models import AttemptStatus
from apps.misconceptions import registry
from apps.misconceptions.domains.python import detectors as python
from apps.misconceptions.evidence import (
    COUNTER,
    POSITIVE,
    EvidenceSignal,
    GenericTagDetector,
    is_safe_details,
)
from apps.misconceptions.tests.helpers import (
    COMPARISON_REFERENCE,
    COMPARISON_TAGS,
    CORRECT,
    INCORRECT,
    choice,
    fake_attempt,
    fake_exercise,
    fill_gap,
    python_code,
)

RANGE_GAP = fill_gap(
    "for n in range(1, __):\n    print(n)", ["6"], ["range-exclusive-stop", "off-by-one"]
)


def detect_all(attempt) -> set[tuple[str, str, str]]:
    return {
        (signal.code, signal.kind, signal.source)
        for detector in registry.detectors()
        for signal in detector.detect(attempt)
    }


def specific(attempt) -> set[tuple[str, str]]:
    """Strong Python signals only: (code, source)."""
    return {
        (signal.code, signal.source)
        for detector in python.DETECTORS
        for signal in detector.detect(attempt)
    }


class GenericTagDetectorTests(SimpleTestCase):
    def setUp(self) -> None:
        self.exercise = fake_exercise(choice(["off-by-one", "loop-condition"]))
        self.detector = GenericTagDetector()

    def test_incorrect_gives_weak_candidates_for_every_tag(self) -> None:
        signals = self.detector.detect(fake_attempt(self.exercise, INCORRECT))
        self.assertEqual(
            [(s.code, s.kind, s.strength, s.source) for s in signals],
            [
                ("off-by-one", POSITIVE, 0.4, "exercise_tag"),
                ("loop-condition", POSITIVE, 0.4, "exercise_tag"),
            ],
        )

    def test_correct_gives_counter_evidence_scaled_by_help(self) -> None:
        def strength(**help_used) -> float:
            return self.detector.detect(fake_attempt(self.exercise, CORRECT, **help_used))[
                0
            ].strength

        independent = strength()
        hint = strength(hint_level=1)
        explanation = strength(used_explanation=True)
        solution = strength(used_solution=True)
        self.assertEqual((independent, hint, explanation, solution), (1.0, 0.9, 0.8, 0.25))
        signal = self.detector.detect(fake_attempt(self.exercise, CORRECT))[0]
        self.assertEqual(signal.kind, COUNTER)

    def test_unjudged_statuses_give_nothing(self) -> None:
        for status in (
            AttemptStatus.INVALID,
            AttemptStatus.UNSUPPORTED,
            AttemptStatus.UNAVAILABLE,
            AttemptStatus.REVIEW_REQUIRED,
        ):
            with self.subTest(status=status):
                self.assertEqual(detect_all(fake_attempt(self.exercise, status)), set())

    def test_untagged_exercises_and_raw_mistakes_give_nothing(self) -> None:
        untagged = fake_exercise(choice([]))
        attempt = fake_attempt(untagged, INCORRECT, diagnostics={"reason": "output_mismatch"})
        attempt.mistakes = ["output_mismatch"]
        self.assertEqual(detect_all(attempt), set())

    def test_malformed_tags_are_ignored(self) -> None:
        exercise = fake_exercise(choice(["ok-code"]))
        exercise.evaluation_spec["misconceptions"] = ["ok-code", "Bad Code", 3, "ok-code"]
        codes = [s.code for s in self.detector.detect(fake_attempt(exercise))]
        self.assertEqual(codes, ["ok-code"])

    def test_signal_contract_rejects_unsafe_values(self) -> None:
        for kwargs in (
            {"code": "Not Safe"},
            {"source": "x y"},
            {"kind": "maybe"},
            {"strength": 1.5},
            {"details": {"answer": "secret"}},
            {"details": {"reason": "print('x')"}},
        ):
            values = {"code": "a", "kind": POSITIVE, "strength": 1.0, "source": "s", **kwargs}
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                EvidenceSignal(**values)


class FillGapOffByOneTests(SimpleTestCase):
    def attempt(self, answer: str, definition=RANGE_GAP, status=INCORRECT):
        return fake_attempt(fake_exercise(definition), status, answer)

    def test_stop_one_lower_in_range_supports_both_codes(self) -> None:
        self.assertEqual(
            specific(self.attempt(" 5 ")),
            {
                ("range-exclusive-stop", "python_fill_gap_off_by_one"),
                ("off-by-one", "python_fill_gap_off_by_one"),
            },
        )

    def test_one_higher_is_only_off_by_one(self) -> None:
        self.assertEqual(
            specific(self.attempt("7")), {("off-by-one", "python_fill_gap_off_by_one")}
        )

    def test_other_values_and_non_ranges(self) -> None:
        self.assertEqual(specific(self.attempt("9")), set())
        self.assertEqual(specific(self.attempt("five")), set())
        self.assertEqual(specific(self.attempt("5", status=CORRECT)), set())
        plain = fill_gap("total = __", ["6"], ["off-by-one", "range-exclusive-stop"])
        self.assertEqual(
            specific(self.attempt("5", definition=plain)),
            {("off-by-one", "python_fill_gap_off_by_one")},
        )

    def test_only_tagged_codes_are_emitted(self) -> None:
        only_range = fill_gap("range(1, __)", ["6"], ["range-exclusive-stop"])
        self.assertEqual(
            specific(self.attempt("5", definition=only_range)),
            {("range-exclusive-stop", "python_fill_gap_off_by_one")},
        )
        untagged = fill_gap("range(1, __)", ["6"], ["loop-variable"])
        self.assertEqual(specific(self.attempt("5", definition=untagged)), set())

    def test_ambiguous_accepted_answers_are_skipped(self) -> None:
        several = fill_gap("range(1, __)", ["6", "7"], ["off-by-one"])
        self.assertEqual(specific(self.attempt("5", definition=several)), set())


class ComparisonTests(SimpleTestCase):
    def gap(self, expected: str, submitted: str, tags=COMPARISON_TAGS):
        exercise = fake_exercise(fill_gap("if age __ 13:", [expected], tags))
        return specific(fake_attempt(exercise, INCORRECT, submitted))

    def code(self, source: str, tags=COMPARISON_TAGS, reference=COMPARISON_REFERENCE):
        exercise = fake_exercise(python_code(reference, tags))
        return specific(fake_attempt(exercise, INCORRECT, source))

    def test_fill_gap_direction_and_boundary(self) -> None:
        direction = {("comparison-direction", "python_comparison_operator")}
        boundary = {("comparison-boundary", "python_comparison_operator")}
        self.assertEqual(self.gap("<", ">"), direction)
        self.assertEqual(self.gap(">=", "<="), direction)
        self.assertEqual(self.gap(">", ">="), boundary)
        self.assertEqual(self.gap("<", "<="), boundary)
        self.assertEqual(self.gap(">", "<="), set())  # negation: ambiguous
        self.assertEqual(self.gap(">", "=="), set())
        self.assertEqual(self.gap(">", "=>"), set())
        self.assertEqual(
            self.gap(
                ">",
                ">",
            ),
            set(),
        )
        self.assertEqual(self.gap("<", ">", tags=["comparison-boundary"]), set())

    def test_code_direction(self) -> None:
        source = COMPARISON_REFERENCE.replace(">", "<")
        self.assertEqual(
            self.code(source), {("comparison-direction", "python_comparison_operator")}
        )

    def test_code_boundary(self) -> None:
        self.assertEqual(
            self.code(COMPARISON_REFERENCE.replace(">", ">=")),
            {("comparison-boundary", "python_comparison_operator")},
        )
        reference = "def f(x):\n    return x < 5\n"
        self.assertEqual(
            self.code("def f(x):\n    return x <= 5\n", reference=reference),
            {("comparison-boundary", "python_comparison_operator")},
        )

    def test_ambiguous_code_gives_nothing(self) -> None:
        # Different structure, other values, two changed operators, negation, broken code.
        self.assertEqual(self.code(COMPARISON_REFERENCE.replace("> 10", "< 11")), set())
        self.assertEqual(self.code(COMPARISON_REFERENCE.replace("print(number)", "pass")), set())
        self.assertEqual(self.code(COMPARISON_REFERENCE.replace(">", "<=")), set())
        two = "def f(a, b):\n    return a > 1 and b > 2\n"
        self.assertEqual(
            self.code("def f(a, b):\n    return a < 1 and b < 2\n", reference=two), set()
        )
        self.assertEqual(self.code("for number in numbers\n    if number < 10:"), set())
        self.assertEqual(self.code(None), set())
        self.assertEqual(self.code(COMPARISON_REFERENCE.replace(">", "<"), reference=None), set())

    def test_non_python_code_is_skipped(self) -> None:
        definition = python_code(COMPARISON_REFERENCE, COMPARISON_TAGS)
        definition["content"]["language"] = "javascript"
        attempt = fake_attempt(fake_exercise(definition), INCORRECT, "if (x < 10) {}")
        self.assertEqual(specific(attempt), set())


class RangeTests(SimpleTestCase):
    STEP_REFERENCE = 'for n in range(10, 0, -1):\n    print(n)\nprint("Lift off!")\n'
    STOP_REFERENCE = "def count_up_to(n):\n    return list(range(1, n + 1))\n"

    def code(self, source: str, reference: str, tags: list[str]):
        exercise = fake_exercise(python_code(reference, tags))
        return specific(fake_attempt(exercise, INCORRECT, source))

    def test_missing_or_wrong_sign_step(self) -> None:
        expected = {("range-step", "python_range_step")}
        missing = self.STEP_REFERENCE.replace(", -1", "")
        self.assertEqual(self.code(missing, self.STEP_REFERENCE, ["range-step"]), expected)
        wrong_sign = self.STEP_REFERENCE.replace("-1", "1")
        self.assertEqual(self.code(wrong_sign, self.STEP_REFERENCE, ["range-step"]), expected)

    def test_other_range_changes_are_not_step_evidence(self) -> None:
        tags = ["range-step"]
        self.assertEqual(
            self.code(self.STEP_REFERENCE.replace("-1", "-2"), self.STEP_REFERENCE, tags), set()
        )
        self.assertEqual(
            self.code(self.STEP_REFERENCE.replace("10, 0", "10, 1"), self.STEP_REFERENCE, tags),
            set(),
        )
        self.assertEqual(self.code("print(10)\n", self.STEP_REFERENCE, tags), set())
        self.assertEqual(
            self.code(self.STEP_REFERENCE.replace(", -1", ""), self.STEP_REFERENCE, ["off-by-one"]),
            set(),
        )

    def test_stop_one_lower(self) -> None:
        tags = ["off-by-one", "range-exclusive-stop"]
        learner = self.STOP_REFERENCE.replace("n + 1", "n")
        self.assertEqual(
            self.code(learner, self.STOP_REFERENCE, tags),
            {("off-by-one", "python_range_stop"), ("range-exclusive-stop", "python_range_stop")},
        )
        literal = "for n in range(2, 21, 2):\n    print(n)\n"
        self.assertEqual(
            self.code(literal.replace("21", "20"), literal, tags),
            {("off-by-one", "python_range_stop"), ("range-exclusive-stop", "python_range_stop")},
        )
        self.assertEqual(
            self.code(literal.replace("21", "22"), literal, tags),
            {("off-by-one", "python_range_stop")},
        )
        self.assertEqual(self.code(literal.replace("21", "25"), literal, tags), set())
        self.assertEqual(self.code(literal.replace("2, 21", "1, 20"), literal, tags), set())


class RuntimeSignalTests(SimpleTestCase):
    WHILE_SOURCE = "n = 1\nwhile n < 5:\n    print(n)\nn = n + 1\n"

    def attempt(self, tags, source, diagnostics):
        exercise = fake_exercise(python_code("n = 1\n", tags))
        return fake_attempt(exercise, INCORRECT, source, diagnostics)

    def test_runaway_while_loop(self) -> None:
        tags = ["infinite-while", "loop-condition"]
        for reason in ("timeout", "output_limit"):
            with self.subTest(reason=reason):
                attempt = self.attempt(tags, self.WHILE_SOURCE, {"reason": reason})
                self.assertEqual(specific(attempt), {("infinite-while", "python_timeout_loop")})
                signal = python.RunawayWhileDetector().detect(attempt)[0]
                self.assertEqual(dict(signal.details), {"reason": reason})

    def test_timeouts_without_tag_or_while_are_not_evidence(self) -> None:
        timeout = {"reason": "timeout"}
        self.assertEqual(
            specific(self.attempt(["loop-condition"], self.WHILE_SOURCE, timeout)), set()
        )
        for_loop = "for n in range(10**9):\n    pass\n"
        self.assertEqual(specific(self.attempt(["infinite-while"], for_loop, timeout)), set())
        self.assertEqual(
            specific(
                self.attempt(["infinite-while"], self.WHILE_SOURCE, {"reason": "output_mismatch"})
            ),
            set(),
        )

    def test_indentation_errors(self) -> None:
        for error_type in ("IndentationError", "TabError"):
            with self.subTest(error_type=error_type):
                attempt = self.attempt(
                    ["indentation-block"],
                    "if x:\nprint(x)\n",
                    {"reason": "runtime_error", "error_type": error_type},
                )
                self.assertEqual(
                    specific(attempt), {("indentation-block", "python_indentation_error")}
                )
                signal = python.IndentationErrorDetector().detect(attempt)[0]
                self.assertEqual(dict(signal.details), {"error_type": error_type})

    def test_other_errors_are_not_indentation_evidence(self) -> None:
        for diagnostics in (
            {"reason": "runtime_error", "error_type": "SyntaxError"},
            {"reason": "runtime_error", "error_type": "NameError"},
            {"reason": "runtime_error"},
        ):
            with self.subTest(diagnostics=diagnostics):
                attempt = self.attempt(["indentation-block"], "if x:\nprint(x)\n", diagnostics)
                self.assertEqual(specific(attempt), set())


class BreakContinueTests(SimpleTestCase):
    REFERENCE = (
        "for n in [1, 2, 3, 4, 5]:\n"
        "    if n == 3:\n        continue\n"
        "    if n == 5:\n        break\n"
        "    print(n)\n"
    )

    def code(self, source: str):
        exercise = fake_exercise(python_code(self.REFERENCE, ["break-vs-continue"]))
        return specific(fake_attempt(exercise, INCORRECT, source))

    def test_single_swap(self) -> None:
        swapped = self.REFERENCE.replace("continue", "break", 1)
        self.assertEqual(self.code(swapped), {("break-vs-continue", "python_break_continue_swap")})

    def test_double_swap_or_other_changes(self) -> None:
        both = (
            self.REFERENCE.replace("continue", "TMP")
            .replace("break", "continue")
            .replace("TMP", "break")
        )
        self.assertEqual(self.code(both), set())
        self.assertEqual(self.code(self.REFERENCE.replace("continue", "pass")), set())
        self.assertEqual(
            self.code(self.REFERENCE.replace("continue", "break").replace("n == 3", "n == 4")),
            set(),
        )


class SafetyTests(SimpleTestCase):
    def test_every_signal_has_safe_details_and_no_answer_text(self) -> None:
        cases = [
            fake_attempt(fake_exercise(RANGE_GAP), INCORRECT, "5"),
            fake_attempt(
                fake_exercise(python_code(COMPARISON_REFERENCE, COMPARISON_TAGS)),
                INCORRECT,
                COMPARISON_REFERENCE.replace(">", "<"),
            ),
            fake_attempt(
                fake_exercise(python_code("x = 1\n", ["infinite-while"])),
                INCORRECT,
                "while True:\n    print('SECRET-LEARNER-CODE')\n",
                {"reason": "timeout"},
            ),
        ]
        for attempt in cases:
            for detector in registry.detectors():
                for signal in detector.detect(attempt):
                    self.assertTrue(is_safe_details(signal.details))
                    text = repr(signal)
                    for secret in ("SECRET", "print", "number", "range("):
                        self.assertNotIn(secret, text)

    def test_detectors_never_execute_code(self) -> None:
        source = "import os\nos.system('echo pwned')\nwhile True:\n    pass\n"
        exercise = fake_exercise(python_code("x = 1\n", ["infinite-while"]))
        with self.assertNoLogs("apps.misconceptions", "ERROR"):
            detect_all(fake_attempt(exercise, INCORRECT, source, {"reason": "timeout"}))
        # Deeply nested or huge input is rejected by the parser guard, not evaluated.
        detect_all(fake_attempt(exercise, INCORRECT, "(" * 5000, {"reason": "timeout"}))
        detect_all(fake_attempt(exercise, INCORRECT, "x" * 70_000, {"reason": "timeout"}))
