import json
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.accounts.tests.helpers import make_user
from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.tests.helpers import ENABLED as TUTOR_ENABLED
from apps.curriculum.tests.helpers import make_concept, make_lesson
from apps.exercises.tests.helpers import make_lesson_chain
from apps.learner_intelligence.models import ConceptState
from apps.learners.models import Enrollment, EnrollmentStatus, LearnerProfile
from apps.projects.evaluation.python import PythonProjectEvaluator
from apps.projects.models import Project, ProjectConceptRequirement, ProjectStage
from apps.python_runner.runner import PythonRunner
from apps.python_runner.tests.fakes import ENABLED as RUNNER_ENABLED
from apps.python_runner.tests.fakes import FakeBackend, outcome

SECRET_EXPECTED = "SECRET-EXPECTED-OUTPUT-7731"
SECRET_DRIVER = "print('SECRET-DRIVER-CODE')"
SECRET_FIXTURE = "id,value\n1,SECRET-FIXTURE-ROW\n"
GOOD = "def area(w, h):\n    return w * h\n"
BAD = "def area(w, h):\n    return w + h\n"


def stdout_spec(expected="ok\n", **extra):
    spec = {
        "strategy": "stdout",
        "tests": [{"stdin": "", "driver": SECRET_DRIVER, "expected_stdout": expected}],
    }
    spec.update(extra)
    return spec


def driver_handler(files, argv, stdin):
    """Fake sandbox: a program 'passes' when it defines area() as a product."""
    source = files["learner.py"]
    marker_line = next(line for line in source.splitlines() if "@@CHECK-" in line)
    marker = marker_line.split("'")[1]
    body = "ok\n" if "w * h" in source else "wrong\n"
    return outcome(stdout=f"noise\n{marker}\n{body}")


class ProjectFixtures:
    """A published World with two concepts and a three-stage project, plus a learner."""

    def setUp(self) -> None:
        super().setUp()
        lesson = make_lesson_chain("Python Foundations", domain="python")
        self.world = lesson.concept.skill.world
        self.skill = lesson.concept.skill
        self.concept_a = lesson.concept
        self.concept_b = make_concept(self.skill, "Loops")
        make_lesson(self.concept_b)

        self.user = make_user("builder")
        self.profile = LearnerProfile.objects.create(user=self.user, preferred_name="Bo")
        self.enrollment = Enrollment.objects.create(learner=self.profile, world=self.world)

        self.project = Project.objects.create(
            world=self.world,
            title="Area Tool",
            slug="area-tool",
            summary="Compute areas.",
            brief="Build an area calculator.",
            order=1,
            estimated_minutes=30,
            xp_reward=150,
            is_published=True,
        )
        for concept in (self.concept_a, self.concept_b):
            ProjectConceptRequirement.objects.create(project=self.project, concept=concept)
        self.stages = [
            ProjectStage.objects.create(
                project=self.project,
                title=f"Stage {n}",
                slug=f"stage-{n}",
                objective=f"Objective {n}",
                instructions=f"Instructions {n}",
                requirements=[f"Requirement {n}"],
                order=n,
                estimated_minutes=10,
                starter_code="def area(w, h):\n    ...\n" if n == 1 else "",
                evaluation_spec=stdout_spec(
                    requires={"functions": ["area"]},
                    fixtures={"data.csv": SECRET_FIXTURE},
                ),
                is_published=True,
            )
            for n in (1, 2, 3)
        ]
        self.backend = self.use_backend(driver_handler)

    # --- helpers -----------------------------------------------------------------------

    def use_backend(self, handler) -> FakeBackend:
        backend = FakeBackend(handler)
        evaluator = PythonProjectEvaluator(
            config_provider=lambda: RUNNER_ENABLED,
            runner_factory=lambda config: PythonRunner(config, backend),
        )
        patcher = mock.patch("apps.projects.services.evaluator_for", return_value=evaluator)
        patcher.start()
        self.addCleanup(patcher.stop)
        return backend

    def master(self, *concepts, score=80, enrollment=None) -> None:
        for concept in concepts or (self.concept_a, self.concept_b):
            ConceptState.objects.update_or_create(
                enrollment=enrollment or self.enrollment,
                concept=concept,
                defaults={"mastery_score": Decimal(str(score)), "evidence_count": 3},
            )

    def enroll_other(self, username="other", status=EnrollmentStatus.ACTIVE):
        user = make_user(username)
        profile = LearnerProfile.objects.create(user=user)
        enrollment = Enrollment.objects.create(learner=profile, world=self.world, status=status)
        return user, enrollment

    def url(self, name, stage=None, world=None, project=None):
        args = [(world or self.world).pk, (project or self.project).slug]
        if stage is not None:
            args.append(stage.slug)
        return reverse(f"projects:{name}", args=args)

    def post(self, url, body, client=None):
        return (client or self.client).post(
            url, data=json.dumps(body), content_type="application/json"
        )

    def submit(self, stage, source=GOOD, client=None, **extra):
        return self.post(self.url("submit", stage), {"source": source, **extra}, client)

    def complete_all(self, client=None):
        for stage in self.stages:
            response = self.submit(stage, client=client)
            assert response.status_code == 201, response.content

    def enable_tutor(self, provider=None) -> FakeTutorProvider:
        provider = provider or FakeTutorProvider()
        self.enterContext(override_settings(AI_TUTOR=TUTOR_ENABLED))
        patcher = mock.patch("apps.projects.coach.get_provider", return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        return provider
