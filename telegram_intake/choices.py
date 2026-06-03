from __future__ import annotations

from typing import Any

from .django_bootstrap import ensure_django

_CACHED_CHOICES: dict[str, Any] | None = None
_LOAD_ERROR: str | None = None


def wizard_choices() -> dict[str, Any]:
    ensure_django()
    from intake.forms import REPRODUCTIVE_STATUS_CHOICES, URGENT_SYMPTOM_CHOICES, Step3Form
    from intake.models import MAIN_REASONS

    step3 = Step3Form()
    return {
        "sex": [("female", "Женский"), ("male", "Мужской")],
        "reproductive": [(code, label) for code, label in REPRODUCTIVE_STATUS_CHOICES if code],
        "urgent": list(URGENT_SYMPTOM_CHOICES),
        "reasons": list(MAIN_REASONS),
        "complaints_started": list(step3.fields["complaints_started"].choices),
        "chronic_conditions": list(step3.fields["chronic_conditions"].choices),
        "medications": list(step3.fields["medications"].choices),
        "allergy_status": list(step3.fields["allergy_status"].choices),
        "family_history": list(step3.fields["family_history"].choices),
        "smoking": list(step3.fields["smoking"].choices),
    }


def preload_wizard_choices() -> bool:
    global _CACHED_CHOICES, _LOAD_ERROR
    try:
        _CACHED_CHOICES = wizard_choices()
        _LOAD_ERROR = None
        return True
    except Exception as exc:
        _CACHED_CHOICES = None
        _LOAD_ERROR = str(exc)
        print(f"Wizard choices preload failed: {exc}", flush=True)
        return False


def get_wizard_choices() -> dict[str, Any]:
    global _CACHED_CHOICES, _LOAD_ERROR
    if _CACHED_CHOICES is not None:
        return _CACHED_CHOICES
    try:
        _CACHED_CHOICES = wizard_choices()
        _LOAD_ERROR = None
    except Exception as exc:
        _LOAD_ERROR = str(exc)
        raise
    return _CACHED_CHOICES


def wizard_choices_error() -> str | None:
    return _LOAD_ERROR
