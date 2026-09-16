from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class User(AbstractUser):
    """Project user model: the authentication identity.

    Learner-specific state lives in ``apps.learners`` (LearnerProfile, Enrollment), not here.
    """

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        constraints = [
            # Non-empty emails are unique regardless of case. Blank emails (e.g. older
            # admin/system accounts) are allowed to repeat.
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="accounts_user_email_ci_unique",
                violation_error_message="A user with this email address already exists.",
            ),
        ]

    def __str__(self) -> str:
        return self.get_username()
