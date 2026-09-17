"""Deterministic Python misconception rules (v1, precision over coverage).

Every rule fires only on an INCORRECT attempt at an exercise whose authored tags include the
code it emits, and only when the evidence is unambiguous. The reference solution is parsed
as hidden context and never copied, logged or returned.
"""

import ast

from apps.attempts.models import AttemptStatus
from apps.exercises.models import ResponseType
from apps.misconceptions import scoring
from apps.misconceptions.domains.python import ast_helpers as tree
from apps.misconceptions.evidence import POSITIVE, EvidenceSignal, exercise_tags

OFF_BY_ONE = "off-by-one"
RANGE_EXCLUSIVE_STOP = "range-exclusive-stop"
COMPARISON_DIRECTION = "comparison-direction"
COMPARISON_BOUNDARY = "comparison-boundary"
RANGE_STEP = "range-step"
INFINITE_WHILE = "infinite-while"
INDENTATION_BLOCK = "indentation-block"
BREAK_VS_CONTINUE = "break-vs-continue"

LOOP_RUNAWAY_REASONS = frozenset({"timeout", "output_limit"})
INDENTATION_ERRORS = frozenset({"IndentationError", "TabError"})
FILL_GAP_OPERATORS = {"<": ast.Lt, "<=": ast.LtE, ">": ast.Gt, ">=": ast.GtE}


def _signals(source: str, codes, tags, pattern: str | None = None, **details):
    if pattern:
        details["pattern"] = pattern
    return [
        EvidenceSignal(code, POSITIVE, scoring.STRONG_STRENGTH, source, details)
        for code in codes
        if code in tags
    ]


def _reason(attempt) -> str | None:
    diagnostics = attempt.diagnostics if isinstance(attempt.diagnostics, dict) else {}
    return diagnostics.get("reason")


def _error_type(attempt) -> str | None:
    diagnostics = attempt.diagnostics if isinstance(attempt.diagnostics, dict) else {}
    return diagnostics.get("error_type")


def _is_python_code(exercise) -> bool:
    content = exercise.content if isinstance(exercise.content, dict) else {}
    return exercise.response_type == ResponseType.CODE and content.get("language") == "python"


def _reference(exercise):
    spec = exercise.evaluation_spec if isinstance(exercise.evaluation_spec, dict) else {}
    return spec.get("reference_solution")


def _accepted(exercise) -> list[str]:
    spec = exercise.evaluation_spec if isinstance(exercise.evaluation_spec, dict) else {}
    answers = spec.get("accepted_answers")
    if not isinstance(answers, list):
        return []
    return [a.strip() for a in answers if isinstance(a, str)]


def _gap_answer(attempt) -> str | None:
    answer = attempt.submitted_answer
    return answer.strip() if isinstance(answer, str) else None


def _parsed_pair(attempt):
    """(learner tree, reference tree) for a Python code attempt, or None."""
    exercise = attempt.exercise
    if not _is_python_code(exercise):
        return None
    learner = tree.parse(attempt.submitted_answer)
    reference = tree.parse(_reference(exercise))
    if learner is None or reference is None:
        return None
    return learner, reference


def _integer(text: str) -> int | None:
    try:
        return int(text) if text.lstrip("+-").isdigit() else None
    except ValueError:
        return None


def _classify_comparison(expected: type, submitted: type) -> str | None:
    """direction / boundary for a single swapped operator; None when ambiguous."""
    if expected is submitted:
        return None
    expected_side, expected_inclusive = tree.COMPARISON_OPS[expected]
    submitted_side, submitted_inclusive = tree.COMPARISON_OPS[submitted]
    if expected_side != submitted_side and expected_inclusive == submitted_inclusive:
        return COMPARISON_DIRECTION
    if expected_side == submitted_side and expected_inclusive != submitted_inclusive:
        return COMPARISON_BOUNDARY
    return None  # e.g. > vs <=: a negation, not clearly either idea


class _PythonDetector:
    name = ""
    codes: frozenset[str] = frozenset()

    def detect(self, attempt) -> list[EvidenceSignal]:
        if attempt.status != AttemptStatus.INCORRECT:
            return []
        tags = set(exercise_tags(attempt.exercise))
        if not tags & self.codes:
            return []
        return self.check(attempt, tags)

    def check(self, attempt, tags: set[str]) -> list[EvidenceSignal]:
        raise NotImplementedError


class FillGapOffByOneDetector(_PythonDetector):
    """The gap needs integer N; the learner typed N-1 or N+1."""

    name = "python_fill_gap_off_by_one"
    codes = frozenset({OFF_BY_ONE, RANGE_EXCLUSIVE_STOP})

    def check(self, attempt, tags):
        exercise = attempt.exercise
        if exercise.response_type != ResponseType.FILL_GAP:
            return []
        expected = {_integer(answer) for answer in _accepted(exercise)}
        submitted = _integer(_gap_answer(attempt) or "")
        if len(expected) != 1 or None in expected or submitted is None:
            return []
        (target,) = expected
        template = (exercise.content or {}).get("template", "")
        in_range = isinstance(template, str) and "range(" in template
        if submitted == target - 1 and in_range:
            return _signals(self.name, (RANGE_EXCLUSIVE_STOP, OFF_BY_ONE), tags, "stop_minus_one")
        if submitted == target - 1:
            return _signals(self.name, (OFF_BY_ONE,), tags, "minus_one")
        if submitted == target + 1:
            return _signals(self.name, (OFF_BY_ONE,), tags, "plus_one")
        return []


class ComparisonOperatorDetector(_PythonDetector):
    """Exactly one comparison operator differs from what the exercise needs."""

    name = "python_comparison_operator"
    codes = frozenset({COMPARISON_DIRECTION, COMPARISON_BOUNDARY})

    def check(self, attempt, tags):
        exercise = attempt.exercise
        if exercise.response_type == ResponseType.FILL_GAP:
            accepted = set(_accepted(exercise))
            submitted = _gap_answer(attempt)
            if len(accepted) != 1 or submitted not in FILL_GAP_OPERATORS:
                return []
            (expected,) = accepted
            if expected not in FILL_GAP_OPERATORS:
                return []
            pair = (FILL_GAP_OPERATORS[expected], FILL_GAP_OPERATORS[submitted])
        else:
            pair = self._code_pair(attempt)
        if pair is None:
            return []
        code = _classify_comparison(*pair)
        return _signals(self.name, (code,), tags, "single_operator") if code else []

    @staticmethod
    def _code_pair(attempt):
        parsed = _parsed_pair(attempt)
        if parsed is None:
            return None
        learner, reference = parsed
        learner_ops, reference_ops = tree.comparison_ops(learner), tree.comparison_ops(reference)
        if len(learner_ops) != len(reference_ops) or not learner_ops:
            return None
        if tree.masked_dump(learner, tree.mask_comparison_ops) != tree.masked_dump(
            reference, tree.mask_comparison_ops
        ):
            return None
        differences = [
            (type(ref), type(own))
            for ref, own in zip(reference_ops, learner_ops, strict=True)
            if type(ref) is not type(own)
        ]
        if len(differences) != 1:
            return None
        expected, submitted = differences[0]
        if expected not in tree.COMPARISON_OPS or submitted not in tree.COMPARISON_OPS:
            return None
        return expected, submitted


def _single_range_difference(attempt):
    """(reference call, learner call) when exactly one range() call differs, else None."""
    parsed = _parsed_pair(attempt)
    if parsed is None:
        return None
    learner, reference = parsed
    learner_calls, reference_calls = tree.range_calls(learner), tree.range_calls(reference)
    if len(learner_calls) != len(reference_calls) or not learner_calls:
        return None
    if tree.masked_dump(learner, tree.mask_range_arguments) != tree.masked_dump(
        reference, tree.mask_range_arguments
    ):
        return None
    differences = [
        (ref, own)
        for ref, own in zip(reference_calls, learner_calls, strict=True)
        if not tree.same_node(ref, own)
    ]
    return differences[0] if len(differences) == 1 else None


class RangeStepDetector(_PythonDetector):
    """The only difference is a missing range step, or a step with the wrong sign."""

    name = "python_range_step"
    codes = frozenset({RANGE_STEP})

    def check(self, attempt, tags):
        pair = _single_range_difference(attempt)
        if pair is None:
            return []
        reference, learner = pair
        if len(reference.args) != 3 or len(learner.args) not in (2, 3):
            return []
        if not all(
            tree.same_node(r, s) for r, s in zip(reference.args[:2], learner.args[:2], strict=True)
        ):
            return []
        if len(learner.args) == 2:
            return _signals(self.name, (RANGE_STEP,), tags, "missing_step")
        expected_sign, learner_sign = tree.sign(reference.args[2]), tree.sign(learner.args[2])
        if expected_sign and learner_sign and expected_sign != learner_sign:
            return _signals(self.name, (RANGE_STEP,), tags, "wrong_step_sign")
        return []


class RangeStopDetector(_PythonDetector):
    """The only difference is a range stop one lower (or higher) than required."""

    name = "python_range_stop"
    codes = frozenset({OFF_BY_ONE, RANGE_EXCLUSIVE_STOP})

    def check(self, attempt, tags):
        pair = _single_range_difference(attempt)
        if pair is None:
            return []
        reference, learner = pair
        if len(reference.args) != len(learner.args) or len(reference.args) < 2:
            return []
        stop = 1
        others_match = all(
            tree.same_node(r, s)
            for index, (r, s) in enumerate(zip(reference.args, learner.args, strict=True))
            if index != stop
        )
        if not others_match:
            return []
        expected, submitted = reference.args[stop], learner.args[stop]
        if self._one_lower(expected, submitted):
            return _signals(self.name, (RANGE_EXCLUSIVE_STOP, OFF_BY_ONE), tags, "stop_minus_one")
        if self._one_lower(submitted, expected):
            return _signals(self.name, (OFF_BY_ONE,), tags, "stop_plus_one")
        return []

    @staticmethod
    def _one_lower(higher: ast.AST, lower: ast.AST) -> bool:
        high, low = tree.int_value(higher), tree.int_value(lower)
        if high is not None and low is not None:
            return high - low == 1
        base = tree.plus_one_base(higher)
        return base is not None and tree.same_node(base, lower)


class RunawayWhileDetector(_PythonDetector):
    """A while loop that never finished (timeout or endless output)."""

    name = "python_timeout_loop"
    codes = frozenset({INFINITE_WHILE})

    def check(self, attempt, tags):
        reason = _reason(attempt)
        if not _is_python_code(attempt.exercise) or reason not in LOOP_RUNAWAY_REASONS:
            return []
        learner = tree.parse(attempt.submitted_answer)
        if learner is None or not tree.has_while(learner):
            return []
        return _signals(self.name, (INFINITE_WHILE,), tags, reason=reason)


class IndentationErrorDetector(_PythonDetector):
    """Python itself rejected the block structure."""

    name = "python_indentation_error"
    codes = frozenset({INDENTATION_BLOCK})

    def check(self, attempt, tags):
        error_type = _error_type(attempt)
        if (
            not _is_python_code(attempt.exercise)
            or _reason(attempt) != "runtime_error"
            or error_type not in INDENTATION_ERRORS
        ):
            return []
        return _signals(self.name, (INDENTATION_BLOCK,), tags, error_type=error_type)


class BreakContinueSwapDetector(_PythonDetector):
    """The code matches the reference except for one break/continue swapped."""

    name = "python_break_continue_swap"
    codes = frozenset({BREAK_VS_CONTINUE})

    def check(self, attempt, tags):
        parsed = _parsed_pair(attempt)
        if parsed is None:
            return []
        learner, reference = parsed
        learner_jumps, reference_jumps = tree.loop_jumps(learner), tree.loop_jumps(reference)
        if len(learner_jumps) != len(reference_jumps) or not learner_jumps:
            return []
        if tree.masked_dump(learner, tree.mask_loop_jumps) != tree.masked_dump(
            reference, tree.mask_loop_jumps
        ):
            return []
        swaps = sum(
            1
            for ref, own in zip(reference_jumps, learner_jumps, strict=True)
            if type(ref) is not type(own)
        )
        return _signals(self.name, (BREAK_VS_CONTINUE,), tags, "swapped") if swaps == 1 else []


DETECTORS = (
    FillGapOffByOneDetector(),
    ComparisonOperatorDetector(),
    RangeStepDetector(),
    RangeStopDetector(),
    RunawayWhileDetector(),
    IndentationErrorDetector(),
    BreakContinueSwapDetector(),
)
