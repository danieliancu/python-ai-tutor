from django.apps import AppConfig


class MisconceptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.misconceptions"
    label = "misconceptions"
    verbose_name = "Misconceptions"

    def ready(self) -> None:
        # Register every domain's misconception catalog and detectors once at startup.
        from apps.misconceptions import registry

        registry.load_domains()
