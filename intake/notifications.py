from __future__ import annotations

from typing import Any

from pathlib import Path

from doctor_notifications import (
    _mime_for_filename,
    notification_status_lines,
    notify_doctor_on_submission,
)

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


def submission_file_attachments(submission: Submission) -> list[tuple[str, bytes, str, str]]:
    attachments: list[tuple[str, bytes, str, str]] = []
    for stored in submission.files.all():
        if not stored.file:
            continue
        filename = Path(stored.file.name).name
        with stored.file.open("rb") as handle:
            content = handle.read()
        maintype, subtype = _mime_for_filename(filename)
        attachments.append((filename, content, maintype, subtype))
    return attachments


def notify_after_submission(submission: Submission) -> list[tuple[bool, str]]:
    submission.refresh_from_db()
    payload = submission_to_notify_payload(submission)
    files = submission_file_attachments(submission)
    return notify_doctor_on_submission(payload, file_attachments=files)


def notify_status_for_doctor(doctor: Doctor | None) -> list[str]:
    return notification_status_lines(doctor_as_notify_dict(doctor))
