from django.apps import AppConfig


class AiTutorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_tutor"
    label = "ai_tutor"
    verbose_name = "AI tutor"

    def ready(self) -> None:
        # Fail fast on invalid settings. This never contacts the provider.
        from apps.ai_tutor.config import get_tutor_config

        get_tutor_config()
