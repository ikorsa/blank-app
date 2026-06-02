from __future__ import annotations

from django import forms

from .branch_fields import fields_for_reason, flatten_branch_data, nested_branch_data


class BranchForm(forms.Form):
    def __init__(self, reasons: list[str], sex: str, *args, branch_initial: dict | None = None, **kwargs):
        self.reasons = [reason for reason in reasons if reason]
        self.sex = sex
        super().__init__(*args, **kwargs)
        for reason in self.reasons:
            for field_name, field in fields_for_reason(reason, sex).items():
                self.fields[f"{reason}__{field_name}"] = field
        if branch_initial:
            for key, value in flatten_branch_data(branch_initial).items():
                if key in self.fields and key not in self.initial:
                    self.initial[key] = value

    def to_branch_dict(self) -> dict[str, dict[str, object]]:
        return nested_branch_data(self.cleaned_data)

    def sections(self) -> list[dict[str, object]]:
        from .branch_fields import REASON_LABELS

        grouped: list[dict[str, object]] = []
        for reason in self.reasons:
            prefix = f"{reason}__"
            bound_fields = [self[field_name] for field_name in self.fields if field_name.startswith(prefix)]
            grouped.append(
                {
                    "code": reason,
                    "label": REASON_LABELS.get(reason, reason),
                    "fields": bound_fields,
                }
            )
        return grouped
