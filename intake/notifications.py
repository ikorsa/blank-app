from __future__ import annotations

from typing import Any

from doctor_notifications import notification_status_lines, notify_doctor_on_submission

from .models import Doctor, Submission
from .summary import build_submission_summary

_SEX_LABELS = {"female": "Женский", "male": "Мужской"}


def doctor_as_notify_dict(doctor: Doctor | None) -> dict[str, Any]:
    if not doctor:
        return {}
    return {
        "id": doctor.slug,
        "name": doctor.name,
        "specialty": doctor.specialty,
        "email": doctor.email,
        "telegram_chat_id": doctor.telegram_chat_id,
    }


def submission_to_notify_payload(submission: Submission) -> dict[str, Any]:
    data = submission.data if isinstance(submission.data, dict) else {}
    step1 = data.get("step1") if isinstance(data.get("step1"), dict) else {}
    step2 = data.get("step2") if isinstance(data.get("step2"), dict) else {}
    reasons = step2.get("main_reasons") if isinstance(step2.get("main_reasons"), list) else []

    return {
        "id": str(submission.id),
        "created_at": submission.created_at.isoformat(timespec="seconds") if submission.created_at else "",
        "assigned_doctor": doctor_as_notify_dict(submission.doctor),
        "main_reasons": reasons,
        "patient": {
            "full_name": step1.get("full_name", ""),
            "phone": step1.get("phone", ""),
            "sex": _SEX_LABELS.get(str(step1.get("sex", "")), step1.get("sex", "")),
            "age": step1.get("age"),
            "city": step1.get("city"),
        },
        "summary": build_submission_summary(data),
    }


def notify_after_submission(submission: Submission) -> list[tuple[bool, str]]:
    return notify_doctor_on_submission(submission_to_notify_payload(submission))


def notify_status_for_doctor(doctor: Doctor | None) -> list[str]:
    return notification_status_lines(doctor_as_notify_dict(doctor))
