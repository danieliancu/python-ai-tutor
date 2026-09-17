from apps.ai_tutor.config import TutorConfig
from apps.ai_tutor.providers.base import TutorProvider


def get_provider(config: TutorConfig) -> TutorProvider:
    """The configured provider. Imported lazily so the SDK loads only when the tutor is used."""
    from apps.ai_tutor.providers.openai import OpenAITutorProvider

    return OpenAITutorProvider(config)
