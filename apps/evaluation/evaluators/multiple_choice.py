from apps.evaluation import results
from apps.evaluation.evaluators.base import config_error, content_of, spec_of
from apps.evaluation.results import EvaluationResult
from apps.exercises.models import Exercise


class MultipleChoiceEvaluator:
    """The answer is the id of one option shown in the exercise content."""

    name = "multiple_choice"

    def evaluate(self, exercise: Exercise, answer: object) -> EvaluationResult:
        option_ids = self._option_ids(exercise)
        correct_option = spec_of(exercise).get("correct_option")
        if not isinstance(correct_option, str) or correct_option not in option_ids:
            raise config_error(exercise, "correct_option is missing or not one of the options")

        if not isinstance(answer, str) or answer.strip() not in option_ids:
            return results.invalid(self.name, "invalid_option", "Choose one of the options shown.")
        if answer.strip() == correct_option:
            return results.correct(self.name)
        return results.incorrect(self.name, "wrong_option")

    @staticmethod
    def _option_ids(exercise: Exercise) -> set[str]:
        options = content_of(exercise).get("options")
        if not isinstance(options, list) or not options:
            raise config_error(exercise, "content has no options")
        ids = {option.get("id") for option in options if isinstance(option, dict)}
        if not all(isinstance(option_id, str) for option_id in ids):
            raise config_error(exercise, "an option has no string id")
        return ids
