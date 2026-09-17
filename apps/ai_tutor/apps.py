from django.apps import AppConfig


class AiTutorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_tutor"
    label = "ai_tutor"
    verbose_name = "AI tutor"

    def ready(self) -> None:
        # Fail fast on invalid settings. This never contacts the provider.
        from apps.ai_tutor.adapters import register_adapter
        from apps.ai_tutor.config import get_tutor_config
        from apps.ai_tutor.domains.python.adapter import PythonTutorAdapter

        get_tutor_config()
        # Domain tutors, selected by World.domain.
        register_adapter(PythonTutorAdapter())
