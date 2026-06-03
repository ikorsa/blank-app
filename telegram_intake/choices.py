from __future__ import annotations

from typing import Any

from .django_bootstrap import ensure_django


def wizard_choices() -> dict[str, Any]:
    ensure_django()
    from intake.forms import REPRODUCTIVE_STATUS_CHOICES, URGENT_SYMPTOM_CHOICES, Step3Form
    from intake.models import MAIN_REASONS

    step3 = Step3Form()
    return {
        "sex": [("female", "Женский"), ("male", "Мужской")],
        "reproductive": [(c, l) for c, l in REPRODUCTIVE_STATUS_CHOICES if c],
        "urgent": list(URGENT_SYMPTOM_CHOICES),
        "reasons": list(MAIN_REASONS),
        "complaints_started": list(step3.fields["complaints_started"].choices),
        "chronic_conditions": list(step3.fields["chronic_conditions"].choices),
        "medications": list(step3.fields["medications"].choices),
        "allergy_status": list(step3.fields["allergy_status"].choices),
        "family_history": list(step3.fields["family_history"].choices),
        "smoking": list(step3.fields["smoking"].choices),
    }
