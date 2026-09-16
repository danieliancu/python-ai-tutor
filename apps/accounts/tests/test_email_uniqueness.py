from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import make_user


class EmailUniquenessConstraintTests(TestCase):
    def test_same_email_in_different_case_is_rejected_by_the_database(self) -> None:
        make_user("daniel", "Daniel@example.com")
        for email in ("daniel@example.com", "DANIEL@EXAMPLE.COM"):
            with (
                self.subTest(email=email),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                User.objects.create_user(username=f"other-{email}", email=email)

    def test_blank_emails_may_repeat(self) -> None:
        User.objects.create_user(username="system-a", email="")
        User.objects.create_user(username="system-b", email="")
        self.assertEqual(User.objects.filter(email="").count(), 2)

    def test_model_validation_reports_the_duplicate(self) -> None:
        make_user("daniel", "daniel@example.com")
        user = User(username="copy", email="DANIEL@example.com")
        user.set_password("irrelevant-pass-123")
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn("A user with this email address already exists.", str(ctx.exception))
