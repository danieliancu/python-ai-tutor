from django.apps import AppConfig


class PythonRunnerConfig(AppConfig):
    name = "apps.python_runner"
    label = "python_runner"
    verbose_name = "Python runner"

    def ready(self) -> None:
        # Fail fast on invalid settings. This never contacts Docker, so the site still starts
        # when the Docker daemon is down.
        from apps.python_runner.config import get_runner_config

        get_runner_config()
