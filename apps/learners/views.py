from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.gamification.selectors import profile_summary
from apps.learners.forms import LearnerProfileForm, OnboardingForm
from apps.learners.services import complete_onboarding, get_or_create_learner_profile


@login_required
@require_http_methods(["GET", "POST"])
def onboarding(request: HttpRequest) -> HttpResponse:
    profile = get_or_create_learner_profile(request.user)
    if profile.has_completed_onboarding:
        return redirect("home")

    if request.method == "POST":
        form = OnboardingForm(request.POST)
        if form.is_valid():
            complete_onboarding(
                profile, form.cleaned_data["preferred_name"], form.cleaned_data["world"]
            )
            return redirect("home")
    else:
        form = OnboardingForm(initial={"preferred_name": profile.display_name})

    return render(request, "learners/onboarding.html", {"form": form, "profile": profile})


@login_required
@require_http_methods(["GET", "POST"])
def profile(request: HttpRequest) -> HttpResponse:
    # Always the signed-in learner: there is no route that takes another learner's id.
    learner = get_or_create_learner_profile(request.user)
    form = LearnerProfileForm(request.POST or None, instance=learner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("learners:profile")

    enrollments = learner.enrollments.select_related("world")
    return render(
        request,
        "learners/profile.html",
        {
            "form": form,
            "profile": learner,
            "enrollments": enrollments,
            "gamification": profile_summary(learner),
        },
    )
