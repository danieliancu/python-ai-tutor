import json
import re
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.ai_tutor.providers.fake import FakeTutorProvider
from apps.ai_tutor.tests.helpers import ENABLED as TUTOR_ENABLED
from apps.attempts.tests.helpers import AttemptFixtures
from apps.exercises.models import LearningMode, ResponseType
from apps.exercises.tests.helpers import make_exercise

CONFIG_SCRIPT = re.compile(
    r'<script id="course-player-config" type="application/json">(.*?)</script>', re.S
)


def player_url(world, exercise=None) -> str:
    url = reverse("course_player:world", args=[world.pk])
    return f"{url}?exercise={exercise.pk}" if exercise is not None else url


def page_config(response) -> dict:
    match = CONFIG_SCRIPT.search(response.content.decode())
    assert match, "course player config missing"
    return json.loads(match.group(1))


class PlayerFixtures(AttemptFixtures):
    """AttemptFixtures (Python, English and Maths worlds) plus a text exercise, signed in."""

    def setUp(self) -> None:
        super().setUp()
        self.concept = self.mcq.lesson.concept
        self.text = make_exercise(
            self.mcq.lesson,
            response_type=ResponseType.TEXT,
            learning_mode=LearningMode.CREATE,
            content={},
            evaluation_spec={"strategy": "rubric", "criteria": ["Explains the idea."]},
        )
        self.client.force_login(self.user)

    def open(self, exercise=None, world=None, client=None):
        return (client or self.client).get(player_url(world or self.python_world, exercise))

    def attempt(self, exercise, body, client=None):
        return (client or self.client).post(
            reverse("attempts:exercise_attempts", args=[exercise.pk]),
            data=json.dumps(body),
            content_type="application/json",
        )

    def tutor(self, body, world=None, client=None):
        return (client or self.client).post(
            reverse("ai_tutor:turns", args=[(world or self.python_world).pk]),
            data=json.dumps(body),
            content_type="application/json",
        )

    def enable_tutor(self, provider=None) -> FakeTutorProvider:
        provider = provider or FakeTutorProvider()
        self.enterContext(override_settings(AI_TUTOR=TUTOR_ENABLED))
        patcher = mock.patch("apps.ai_tutor.services.get_provider", return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        return provider
