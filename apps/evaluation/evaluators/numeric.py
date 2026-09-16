from decimal import Decimal, InvalidOperation

from apps.evaluation import results
from apps.evaluation.evaluators.base import config_error, spec_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise

# Numbers beyond ±1e100 (or finer than 1e-100) aren't meaningful answers, and rejecting them
# keeps Decimal arithmetic away from overflow and huge inputs.
MAX_ABS_EXPONENT = 100
MAX_TEXT_LENGTH = 100


def to_decimal(value: object, *, allow_text: bool) -> Decimal | None:
    """A finite Decimal of sensible magnitude, or None if the value isn't a usable number.

    Booleans are rejected even though bool is a subclass of int. Floats go through str()
    so 0.1 becomes Decimal("0.1") rather than its binary approximation.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, float):
        number = Decimal(str(value))
    elif allow_text and isinstance(value, str) and 0 < len(value.strip()) <= MAX_TEXT_LENGTH:
        try:
            number = Decimal(value.strip())
        except InvalidOperation:
            return None
    else:
        return None
    if not number.is_finite():
        return None
    if number and abs(number.adjusted()) > MAX_ABS_EXPONENT:
        return None
    return number


class NumericEvaluator:
    """The answer is a number (or numeric text) compared within an optional tolerance."""

    name = "numeric"

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        spec = spec_of(exercise)
        expected = to_decimal(spec.get("expected"), allow_text=False)
        if expected is None:
            raise config_error(exercise, "expected must be a finite number")
        tolerance = to_decimal(spec.get("tolerance", 0), allow_text=False)
        if tolerance is None or tolerance < 0:
            raise config_error(exercise, "tolerance must be a finite number of zero or more")

        submitted = to_decimal(answer, allow_text=True)
        if submitted is None:
            return results.invalid(self.name, "invalid_numeric_input", "Enter a valid number.")
        if abs(submitted - expected) <= tolerance:
            return results.correct(self.name)
        return results.incorrect(self.name, "incorrect_value")
