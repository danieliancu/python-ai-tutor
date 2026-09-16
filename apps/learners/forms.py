import zoneinfo
from functools import cache

from django import forms

from apps.curriculum.models import World
from apps.learners.models import LearnerProfile
from config.forms import AccessibleFormMixin


@cache
def timezone_choices() -> list[tuple[str, str]]:
    names = zoneinfo.available_timezones() | {"UTC"}
    return [(name, name.replace("_", " ")) for name in sorted(names)]


class WorldChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: World) -> str:
        return obj.title


class OnboardingForm(AccessibleFormMixin, forms.Form):
    preferred_name = forms.CharField(
        label="What would you like us to call you?",
        max_length=80,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    world = WorldChoiceField(
        label="Choose what you want to learn",
        queryset=World.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        error_messages={"invalid_choice": "Choose one of the available learning paths."},
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Only published Worlds can be joined; the queryset is also what validates the POST.
        worlds = World.objects.filter(is_published=True).order_by("order", "id")
        self.fields["world"].queryset = worlds
        if not self.is_bound and len(worlds) == 1:
            self.initial.setdefault("world", worlds[0].pk)
        # Radio buttons are styled as cards, not text inputs.
        self.fields["world"].widget.attrs.pop("class", None)

    @property
    def has_worlds(self) -> bool:
        return self.fields["world"].queryset.exists()


class LearnerProfileForm(AccessibleFormMixin, forms.ModelForm):
    timezone = forms.ChoiceField(label="Time zone", choices=timezone_choices)

    class Meta:
        model = LearnerProfile
        fields = ["preferred_name", "timezone"]
        labels = {"preferred_name": "Preferred name"}
        help_texts = {"preferred_name": "How we greet you. Leave blank to use your username."}
        widgets = {"preferred_name": forms.TextInput(attrs={"autocomplete": "name"})}
