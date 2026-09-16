from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.models import User


class SignUpForm(UserCreationForm):
    """Collect the small amount of information needed to create an account."""

    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email
