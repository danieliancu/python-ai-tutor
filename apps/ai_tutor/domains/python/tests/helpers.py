from apps.ai_tutor.tests.helpers import TutorFixtures
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise

FUNCTION_SECRET = "SECRET-HIDDEN-RETURN-VALUE"
FUNCTION_REFERENCE = "def count_up_to(n):\n    return list(range(1, n + 1))\n"
FUNCTION_SOURCE = "def count_up_to(n):\n    return list(range(1, n))\n"


class PythonTutorFixtures(TutorFixtures):
    """TutorFixtures with the Python World marked as the ``python`` domain."""

    def setUp(self) -> None:
        super().setUp()
        self.python_world.domain = "python"
        self.python_world.save()
        self.enrollment.world.refresh_from_db()
        self.function = make_exercise(
            self.mcq.lesson,
            response_type=ResponseType.CODE,
            learning_mode=LearningMode.FIX,
            content={"language": "python", "starter_code": FUNCTION_SOURCE},
            evaluation_spec={
                "strategy": "function",
                "function_name": "count_up_to",
                "tests": [
                    {"args": [3], "kwargs": {}, "expected": [1, 2, 3]},
                    {"args": [0], "kwargs": {}, "expected": FUNCTION_SECRET},
                ],
                "reference_solution": FUNCTION_REFERENCE,
                "misconceptions": ["off-by-one", "range-exclusive-stop"],
            },
        )

    def climb(self, exercise, target: str):
        """Request solution help until the server grants ``target``; returns that request."""
        for _ in range(4):
            outcome = self.tutor("solution", exercise=exercise)
            if outcome.turn.response_kind == target:
                return self.last_request()
        raise AssertionError(f"{target} was never granted")
