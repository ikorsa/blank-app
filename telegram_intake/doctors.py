from __future__ import annotations

from anamnes_storage import load_doctors as load_legacy_doctors

from .django_bootstrap import ensure_django


def load_doctors(*, include_inactive: bool = False) -> list[dict[str, str]]:
    try:
        ensure_django()
        from intake.models import Doctor

        qs = Doctor.objects.all().order_by("name")
        if not include_inactive:
            qs = qs.filter(is_active=True)
        doctors = [
            {
                "id": doctor.slug,
                "name": doctor.name,
                "specialty": doctor.specialty,
                "email": doctor.email,
                "telegram_chat_id": doctor.telegram_chat_id,
                "password": doctor.password,
                "is_active": "true" if doctor.is_active else "false",
            }
            for doctor in qs
        ]
        if doctors:
            return doctors
    except Exception:
        pass
    return load_legacy_doctors(include_inactive=include_inactive)


def get_doctor(doctor_id: str, *, include_inactive: bool = False) -> dict[str, str] | None:
    doctor_id = doctor_id.strip().lower()
    return next(
        (doctor for doctor in load_doctors(include_inactive=include_inactive) if doctor["id"] == doctor_id),
        None,
    )
