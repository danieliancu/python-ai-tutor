from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, resolve_url
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView

from apps.accounts.forms import (
    EmailOrUsernameAuthenticationForm,
    NewPasswordForm,
    PasswordResetRequestForm,
    SignUpForm,
)
from apps.learners.services import get_or_create_learner_profile, needs_onboarding


class SignUpView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignUpForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SignUpForm) -> HttpResponse:
        with transaction.atomic():
            user = form.save()
            get_or_create_learner_profile(user)
        login(self.request, user)
        return redirect("learners:onboarding")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        user = self.request.user
        if user.is_authenticated and needs_onboarding(user):
            return reverse("learners:onboarding")
        # get_redirect_url() only returns `next` when it is safe for this host.
        return self.get_redirect_url() or resolve_url("home")


class LogoutView(auth_views.LogoutView):
    """POST-only (Django 5); redirects to LOGOUT_REDIRECT_URL."""


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
