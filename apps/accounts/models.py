from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model.

    Intentionally identical to Django's default for now; defined up front so fields
    can be added later without swapping AUTH_USER_MODEL mid-project.
    """

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"

    def __str__(self) -> str:
        return self.get_username()
