from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from .models import Draft, Submission, SubmissionFile

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9._-]+", "_", name).strip("._")
    return cleaned or "file"


def upload_bucket(request: HttpRequest, draft: Draft | None) -> str:
    if draft:
        return f"draft_{draft.id}"
    if not request.session.session_key:
        request.session.save()
    return f"session_{request.session.session_key}"


def pending_dir(bucket: str) -> Path:
    path = Path(settings.MEDIA_ROOT) / "pending_uploads" / bucket
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_upload(uploaded: UploadedFile) -> str | None:
    name = uploaded.name or "file"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Файл «{name}»: допустимы только PDF, JPG, PNG."
    if uploaded.size > MAX_UPLOAD_BYTES:
        return f"Файл «{name}»: размер больше 25 МБ."
    return None


def save_uploads(bucket: str, uploaded_files: list[UploadedFile]) -> tuple[list[dict[str, Any]], list[str]]:
    saved: list[dict[str, Any]] = []
    errors: list[str] = []
    directory = pending_dir(bucket)

    for uploaded in uploaded_files:
        if not uploaded:
            continue
        error = _validate_upload(uploaded)
        if error:
            errors.append(error)
            continue

        original_name = uploaded.name or "file"
        stored_name = f"{uuid.uuid4().hex}_{safe_filename(original_name)}"
        target = directory / stored_name
        with target.open("wb") as handle:
            for chunk in uploaded.chunks():
                handle.write(chunk)

        saved.append(
            {
                "stored_name": stored_name,
                "original_name": original_name,
                "size": uploaded.size,
                "content_type": getattr(uploaded, "content_type", "") or "",
            }
        )
    return saved, errors


def merge_pending_files(existing: Any, new_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = list(existing) if isinstance(existing, list) else []
    pending.extend(new_items)
    return pending


def pending_file_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    pending = data.get("pending_files")
    return list(pending) if isinstance(pending, list) else []


def attach_pending_files_to_submission(
    submission: Submission,
    bucket: str,
    records: list[dict[str, Any]],
    extra_uploads: list[UploadedFile] | None = None,
) -> tuple[int, list[str]]:
    errors: list[str] = []
    count = 0
    directory = pending_dir(bucket)

    for record in records:
        if not isinstance(record, dict):
            continue
        stored_name = str(record.get("stored_name") or "")
        original_name = str(record.get("original_name") or stored_name)
        path = directory / stored_name
        if not path.is_file():
            errors.append(f"Файл «{original_name}» не найден на сервере, загрузите снова.")
            continue
        SubmissionFile.objects.create(
            submission=submission,
            file=ContentFile(path.read_bytes(), name=safe_filename(original_name)),
        )
        count += 1

    if extra_uploads:
        saved, upload_errors = save_uploads(f"submission_{submission.id}", extra_uploads)
        errors.extend(upload_errors)
        submit_dir = pending_dir(f"submission_{submission.id}")
        for item in saved:
            path = submit_dir / item["stored_name"]
            if path.is_file():
                SubmissionFile.objects.create(
                    submission=submission,
                    file=ContentFile(path.read_bytes(), name=safe_filename(item["original_name"])),
                )
                count += 1

    return count, errors


def clear_pending_uploads(bucket: str) -> None:
    directory = pending_dir(bucket)
    if not directory.exists():
        return
    for path in directory.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)
    try:
        directory.rmdir()
    except OSError:
        pass
