from apps.evaluation import results
from apps.evaluation.evaluators.base import config_error, spec_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise


class FillGapEvaluator:
    """The answer is the text that belongs in the gap.

    Surrounding whitespace is ignored. Comparison is exact unless the spec sets
    ``case_sensitive`` to false, in which case Unicode case folding is used.
    """

    name = "fill_gap"

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        spec = spec_of(exercise)
        accepted = spec.get("accepted_answers")
        if (
            not isinstance(accepted, list)
            or not accepted
            or not all(isinstance(item, str) and item.strip() for item in accepted)
        ):
            raise config_error(exercise, "accepted_answers must be a list of non-empty strings")
        case_sensitive = spec.get("case_sensitive", True)
        if not isinstance(case_sensitive, bool):
            raise config_error(exercise, "case_sensitive must be a boolean")

        if not isinstance(answer, str):
            return results.invalid(self.name, "invalid_answer_type", "Type your answer as text.")
        submitted = answer.strip()
        if not submitted:
            return results.invalid(self.name, "empty_answer", "Type an answer in the gap.")

        accepted = [item.strip() for item in accepted]
        folded = submitted.casefold()
        if case_sensitive:
            if submitted in accepted:
                return results.correct(self.name)
            if any(folded == item.casefold() for item in accepted):
                return results.incorrect(self.name, "case_mismatch")
        elif any(folded == item.casefold() for item in accepted):
            return results.correct(self.name)
        return results.incorrect(self.name, "incorrect_value")
