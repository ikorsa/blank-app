from __future__ import annotations

from typing import Any

from django import forms

from .branch_fields import BRANCH_BUILDERS
from .forms import Step3Form


def _labels_from_choices(choices: list[tuple[str, str]] | tuple) -> dict[str, str]:
    labels: dict[str, str] = {}
    for code, label in choices:
        code_str = str(code)
        if code_str == "":
            continue
        labels[code_str] = str(label)
    return labels


def _labels_from_field(field: forms.Field) -> dict[str, str]:
    choices = getattr(field, "choices", None)
    if not choices:
        return {}
    return _labels_from_choices(list(choices))


def build_step3_choice_labels() -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    for name, field in Step3Form.base_fields.items():
        field_labels = _labels_from_field(field)
        if field_labels:
            labels[name] = field_labels
    return labels


def build_branch_choice_labels() -> dict[tuple[str, str], dict[str, str]]:
    labels: dict[tuple[str, str], dict[str, str]] = {}
    for reason, builder in BRANCH_BUILDERS.items():
        merged_fields: dict[str, forms.Field] = {}
        for sex in ("female", "male"):
            merged_fields.update(builder(sex))
        for field_name, field in merged_fields.items():
            field_labels = _labels_from_field(field)
            if field_labels:
                labels[(reason, field_name)] = field_labels
    return labels


STEP3_CHOICE_LABELS = build_step3_choice_labels()
BRANCH_CHOICE_LABELS = build_branch_choice_labels()


def format_labeled_value(value: Any, labels: dict[str, str] | None) -> str:
    if value is None or value == "":
        return "не указано"
    if not labels:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "не указано"
        return str(value)

    if isinstance(value, list):
        mapped = [labels.get(str(item), str(item)) for item in value]
        return ", ".join(mapped) if mapped else "не указано"

    return labels.get(str(value), str(value))


def format_step3_value(field_name: str, value: Any) -> str:
    return format_labeled_value(value, STEP3_CHOICE_LABELS.get(field_name))


def format_branch_value(reason: str, field_name: str, value: Any) -> str:
    return format_labeled_value(value, BRANCH_CHOICE_LABELS.get((reason, field_name)))
