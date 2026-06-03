from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile

from .api import download_file
from .django_bootstrap import ensure_django
from .session import clear_session


def submit_session(session: dict[str, Any]) -> tuple[str, list[tuple[bool, str]]]:
    ensure_django()
    from intake.models import Doctor, Submission, SubmissionFile
    from intake.notifications import notify_after_submission

    doctor_slug = str(session.get("doctor_id") or "").strip().lower()
    doctor = Doctor.objects.filter(slug=doctor_slug, is_active=True).first()
    if not doctor and doctor_slug:
        doctor = Doctor.objects.filter(slug=doctor_slug).first()

    data = session.get("data") if isinstance(session.get("data"), dict) else {}
    data.setdefault("step5", {})
    if session.get("pending_files"):
        data["step5"]["telegram_files"] = [
            {"original_name": item.get("original_name"), "telegram_file_id": item.get("telegram_file_id")}
            for item in session["pending_files"]
            if isinstance(item, dict)
        ]

    submission = Submission.objects.create(doctor=doctor, data=data)
    for item in session.get("pending_files") or []:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("telegram_file_id") or "")
        if not file_id:
            continue
        try:
            content, remote_name = download_file(file_id)
        except Exception:
            continue
        original_name = str(item.get("original_name") or remote_name or "file.bin")
        ext = Path(original_name).suffix or Path(remote_name).suffix or ".bin"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        SubmissionFile.objects.create(
            submission=submission,
            file=ContentFile(content, name=safe_name),
        )

    notify_results = notify_after_submission(submission)
    clear_session(int(session["chat_id"]))
    return str(submission.id), notify_results
