"""Form helpers shared by the project's apps."""


class AccessibleFormMixin:
    """Give every widget the shared input class and link invalid inputs to their errors.

    Pairs with ``templates/includes/field.html``, which renders errors with the id
    ``<auto_id>_error`` and help text with ``<auto_id>_helptext``.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} field__input".strip()

    def full_clean(self) -> None:
        super().full_clean()
        for name in self.errors:
            if name not in self.fields:
                continue
            bound = self[name]
            described_by = [f"{bound.auto_id}_error"]
            if bound.help_text:
                described_by.append(f"{bound.auto_id}_helptext")
            attrs = self.fields[name].widget.attrs
            attrs["aria-invalid"] = "true"
            attrs["aria-describedby"] = " ".join(described_by)
