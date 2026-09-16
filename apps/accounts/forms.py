from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from apps.accounts.models import User
from config.forms import AccessibleFormMixin


def _set_autocomplete(form: forms.Form, **values: str) -> None:
    for name, value in values.items():
        form.fields[name].widget.attrs["autocomplete"] = value


class SignUpForm(AccessibleFormMixin, UserCreationForm):
    email = forms.EmailField(label="Email", max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _set_autocomplete(
            self,
            username="username",
            email="email",
            password1="new-password",
            password2="new-password",
        )

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"].strip())
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists.", code="duplicate_email"
            )
        return email


class EmailOrUsernameAuthenticationForm(AccessibleFormMixin, AuthenticationForm):
    """Django's login form, accepting either a username or a (case-insensitive) email."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "That email or username and password don't match. Check them and try again."
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email or username"
        _set_autocomplete(self, username="username", password="current-password")

    def clean(self):
        identifier = (self.cleaned_data.get("username") or "").strip()
        if identifier and not User.objects.filter(username=identifier).exists():
            username = (
                User.objects.filter(email__iexact=identifier)
                .exclude(email="")
                .values_list("username", flat=True)
                .first()
            )
            if username is not None:
                self.cleaned_data["username"] = username
        # Normal Django authentication: backend lookup, password hashing, is_active checks.
        return super().clean()


class PasswordResetRequestForm(AccessibleFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _set_autocomplete(self, email="email")


class NewPasswordForm(AccessibleFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _set_autocomplete(self, new_password1="new-password", new_password2="new-password")
