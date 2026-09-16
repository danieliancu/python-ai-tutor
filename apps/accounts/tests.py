from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_custom_user_model_is_active(self) -> None:
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertIs(get_user_model(), User)

    def test_create_user(self) -> None:
        user = User.objects.create_user(
            username="alice", email="alice@example.com", password="s3cure-pass-123"
        )

        self.assertEqual(user.username, "alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, "s3cure-pass-123")
        self.assertTrue(user.check_password("s3cure-pass-123"))
        self.assertEqual(str(user), "alice")

    def test_create_superuser(self) -> None:
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="s3cure-pass-123"
        )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
