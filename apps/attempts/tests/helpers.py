from unittest import mock

from apps.accounts.tests.helpers import make_user
from apps.attempts.services import record_attempt
from apps.evaluation import registry
from apps.evaluation.evaluators.code import CodeEvaluator
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise, make_lesson_chain
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile
from apps.python_runner.evaluator import PythonCodeEvaluator
from apps.python_runner.exceptions import RunnerUnavailableError
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import ENABLED, FakeBackend

SECRET_OPTION = "opt-secret-b"
SECRET_GAP = "gap-secret-answer"
SECRET_NUMBER = 4321.25
SECRET_OUTPUT = "SECRET-EXPECTED-STDOUT"
SECRET_SOLUTION = "SECRET-REFERENCE-SOLUTION"


class AttemptFixtures:
    """Mixin for TestCase: one learner enrolled in Python, English and Maths worlds."""

    def setUp(self) -> None:
        super().setUp()
        self.user = make_user("learner")
        self.profile = LearnerProfile.objects.create(user=self.user)

        python_lesson = make_lesson_chain("Python Foundations")
        english_lesson = make_lesson_chain("English A1")
        maths_lesson = make_lesson_chain("Maths Foundations")
        self.python_world = python_lesson.concept.skill.world
        self.english_world = english_lesson.concept.skill.world
        self.maths_world = maths_lesson.concept.skill.world

        self.enrollment = self.enroll(self.python_world)
        self.english_enrollment = self.enroll(self.english_world)
        self.maths_enrollment = self.enroll(self.maths_world)

        self.mcq = make_exercise(
            python_lesson,
            response_type=ResponseType.MULTIPLE_CHOICE,
            learning_mode=LearningMode.RECOGNISE,
            content={
                "options": [
                    {"id": "opt-a", "text": "value > 10"},
                    {"id": SECRET_OPTION, "text": "value >= 10"},
                ]
            },
            evaluation_spec={"correct_option": SECRET_OPTION, "explanation": "inclusive"},
        )
        self.gap = make_exercise(
            python_lesson,
            response_type=ResponseType.FILL_GAP,
            learning_mode=LearningMode.COMPLETE,
            content={"template": "print(__)"},
            evaluation_spec={"accepted_answers": [SECRET_GAP], "case_sensitive": True},
        )
        self.code = make_exercise(
            python_lesson,
            response_type=ResponseType.CODE,
            learning_mode=LearningMode.CREATE,
            content={"language": "python", "starter_code": "# write here\n"},
            evaluation_spec={
                "strategy": "stdout",
                "tests": [{"stdin": "", "expected_stdout": SECRET_OUTPUT + "\n"}],
                "reference_solution": f"print('{SECRET_SOLUTION}')\n",
            },
        )
        self.translation = make_exercise(
            english_lesson,
            response_type=ResponseType.TRANSLATION,
            learning_mode=LearningMode.CREATE,
            content={"source_language": "ro", "target_language": "en-GB", "source_text": "Salut"},
            evaluation_spec={"reference_answers": ["Hello"]},
        )
        self.numeric = make_exercise(
            maths_lesson,
            response_type=ResponseType.NUMERIC,
            learning_mode=LearningMode.CREATE,
            content={"unit": "cm"},
            evaluation_spec={"expected": SECRET_NUMBER, "tolerance": 0.05},
        )

    def enroll(self, world, status=EnrollmentStatus.ACTIVE) -> Enrollment:
        return Enrollment.objects.create(learner=self.profile, world=world, status=status)

    def record(self, exercise, answer, user=None, **kwargs):
        return record_attempt(user=user or self.user, exercise=exercise, answer=answer, **kwargs)

    def use_python_backend(self, handler) -> FakeBackend:
        """Route Python code through PythonCodeEvaluator with a fake (Docker-free) backend."""
        backend = FakeBackend(handler)
        python = PythonCodeEvaluator(
            config_provider=lambda: ENABLED,
            runner_factory=lambda config: PythonRunner(config, backend),
        )
        patcher = mock.patch.dict(
            registry.EVALUATORS, {ResponseType.CODE: CodeEvaluator({"python": python})}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return backend

    def break_python_runner(self) -> None:
        def down(*args):
            raise RunnerUnavailableError("docker: Cannot connect to the Docker daemon")

        self.use_python_backend(down)
