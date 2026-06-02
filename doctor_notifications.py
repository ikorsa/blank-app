"""Email and Telegram notifications to doctors on new submissions."""

from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

SMTP_HOST = os.getenv("ANAMNES_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("ANAMNES_SMTP_PORT", "587"))
SMTP_USER = os.getenv("ANAMNES_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("ANAMNES_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("ANAMNES_SMTP_FROM", SMTP_USER)
SMTP_TO = os.getenv("ANAMNES_SMTP_TO", "")
PUBLIC_URL = os.getenv("ANAMNES_PUBLIC_URL", "https://anamnes.ikorsakov.tech").rstrip("/")
TELEGRAM_CHAT_ID = os.getenv("ANAMNES_TELEGRAM_CHAT_ID", "")
MAX_EMAIL_ATTACH_BYTES = 20 * 1024 * 1024
ATTACH_JSON_IN_EMAIL = os.getenv("ANAMNES_EMAIL_ATTACH_JSON", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _mime_for_filename(filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application", "pdf"
    if ext in {".jpg", ".jpeg"}:
        return "image", "jpeg"
    if ext == ".png":
        return "image", "png"
    return "application", "octet-stream"


def telegram_notify_token() -> str:
    """Doctor alerts: dedicated bot token, or the patient bot if only one is configured."""
    return os.getenv("ANAMNES_TELEGRAM_BOT_TOKEN", "") or os.getenv(
        "ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN", ""
    )


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM)


def doctor_email_ready(doctor: dict[str, Any] | None) -> bool:
    if not smtp_configured():
        return False
    doctor = doctor or {}
    return bool(str(doctor.get("email") or "").strip() or SMTP_TO)


def doctor_telegram_ready(doctor: dict[str, Any] | None) -> bool:
    if not telegram_notify_token():
        return False
    doctor = doctor or {}
    return bool(str(doctor.get("telegram_chat_id") or "").strip() or TELEGRAM_CHAT_ID)


def notification_status_lines(doctor: dict[str, Any] | None) -> list[str]:
    doctor = doctor or {}
    lines: list[str] = []
    if doctor_email_ready(doctor):
        target = doctor.get("email") or SMTP_TO
        lines.append(f"Email: будет отправляться на **{target}**")
    elif smtp_configured():
        lines.append("Email: у врача не указан адрес (заполните в карточке или ANAMNES_SMTP_TO)")
    else:
        lines.append("Email: SMTP не настроен (ANAMNES_SMTP_* в /etc/anamnes.env)")

    if doctor_telegram_ready(doctor):
        cid = doctor.get("telegram_chat_id") or TELEGRAM_CHAT_ID
        lines.append(f"Telegram: уведомления на chat_id `{cid}`")
    elif telegram_notify_token():
        lines.append(
            "Telegram: токен бота есть, но нет chat_id врача. "
            "Врач пишет боту /start, затем узнайте chat_id (@userinfobot) и укажите в карточке."
        )
    else:
        lines.append(
            "Telegram: задайте ANAMNES_TELEGRAM_BOT_TOKEN или ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN"
        )
    return lines


def format_answer(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def send_submission_email(
    submission: dict[str, Any],
    file_attachments: list[tuple[str, bytes, str, str]] | None = None,
) -> tuple[bool, str]:
    doctor = submission.get("assigned_doctor", {}) or {}
    recipient = str(doctor.get("email") or "").strip() or SMTP_TO
    if not smtp_configured():
        return False, "SMTP не настроен: задайте ANAMNES_SMTP_* в окружении."
    if not recipient:
        return False, "Нет email врача и не задан ANAMNES_SMTP_TO."

    patient = submission.get("patient", {})
    reason = ", ".join(submission.get("main_reasons") or []) or "—"
    submission_id = submission.get("id", "")
    subject = f"Новая анкета эндокринолога: {patient.get('full_name', 'без имени')}"

    attached_names: list[str] = []
    skipped_names: list[str] = []
    total_bytes = 0

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = recipient
    if SMTP_TO and SMTP_TO.strip().lower() != recipient.strip().lower():
        message["Bcc"] = SMTP_TO.strip()

    summary_text = str(submission.get("summary") or "")
    body_lines = [
        "Получена новая анкета пациента.",
        "",
        f"Пациент: {format_answer(patient.get('full_name'))}",
        f"Телефон: {format_answer(patient.get('phone'))}",
        f"Причина обращения: {reason}",
        f"ID анкеты: {submission_id}",
        f"Дата UTC: {submission.get('created_at', '')}",
        "",
        "Краткое резюме — во вложении anamnes_*.txt",
        f"Кабинет на сайте: {PUBLIC_URL}/doctor/",
    ]
    message.set_content("\n".join(body_lines))

    summary_bytes = summary_text.encode("utf-8")
    message.add_attachment(
        summary_bytes,
        maintype="text",
        subtype="plain",
        filename=f"anamnes_{submission_id}.txt",
    )
    attached_names.append(f"anamnes_{submission_id}.txt")
    total_bytes += len(summary_bytes)

    for filename, content, maintype, subtype in file_attachments or []:
        if total_bytes + len(content) > MAX_EMAIL_ATTACH_BYTES:
            skipped_names.append(filename)
            continue
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )
        attached_names.append(filename)
        total_bytes += len(content)

    if ATTACH_JSON_IN_EMAIL:
        raw = json.dumps(submission, ensure_ascii=False, indent=2).encode("utf-8")
        if total_bytes + len(raw) <= MAX_EMAIL_ATTACH_BYTES:
            message.add_attachment(
                raw,
                maintype="application",
                subtype="json",
                filename=f"submission_{submission_id}.json",
            )
            attached_names.append(f"submission_{submission_id}.json")
            total_bytes += len(raw)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)

    parts = [f"Письмо отправлено на {recipient}."]
    if attached_names:
        parts.append(f"Вложения: {', '.join(attached_names)}.")
    if skipped_names:
        parts.append(
            f"Не влезли в лимит 20 МБ (откройте в кабинете): {', '.join(skipped_names)}."
        )
    return True, " ".join(parts)


def send_telegram_notification(submission: dict[str, Any]) -> tuple[bool, str]:
    token = telegram_notify_token()
    doctor = submission.get("assigned_doctor", {}) or {}
    chat_id = str(doctor.get("telegram_chat_id") or "").strip() or TELEGRAM_CHAT_ID
    if not token:
        return False, "Telegram: не задан токен бота."
    if not chat_id:
        return False, "Telegram: не указан chat_id врача."

    patient = submission.get("patient", {})
    reason = ", ".join(submission.get("main_reasons") or []) or "—"
    text = "\n".join(
        [
            "Новая анкета эндокринолога",
            f"Пациент: {format_answer(patient.get('full_name'))}",
            f"Телефон: {format_answer(patient.get('phone'))}",
            f"Причина: {reason}",
            f"ID: {submission['id']}",
            f"Кабинет: {PUBLIC_URL}",
        ]
    )
    payload = urlencode({"chat_id": chat_id, "text": text})
    url = f"https://api.telegram.org/bot{token}/sendMessage?{payload}"
    with urlopen(url, timeout=15) as response:
        if response.status != 200:
            return False, f"Telegram вернул HTTP {response.status}."
    return True, "Telegram-уведомление отправлено."


def send_test_notifications(doctor: dict[str, Any]) -> list[tuple[bool, str]]:
    """Send test messages using the same channels as real submissions."""
    test_submission = {
        "id": "test-notification",
        "created_at": "—",
        "patient": {"full_name": "Тест уведомления", "phone": "+7 000 000-00-00"},
        "main_reasons": ["Проверка настроек"],
        "summary": "Это тестовое сообщение из раздела «Управление врачами».",
        "assigned_doctor": doctor,
    }
    results: list[tuple[bool, str]] = []
    if doctor_email_ready(doctor):
        try:
            results.append(send_submission_email(test_submission))
        except Exception as exc:
            results.append((False, f"Email: {exc}"))
    else:
        results.append((False, "Email: канал не настроен для этого врача."))

    if doctor_telegram_ready(doctor):
        try:
            results.append(send_telegram_notification(test_submission))
        except Exception as exc:
            results.append((False, f"Telegram: {exc}"))
    else:
        results.append((False, "Telegram: канал не настроен для этого врача."))
    return results


def notify_doctor_on_submission(
    submission: dict[str, Any],
    file_attachments: list[tuple[str, bytes, str, str]] | None = None,
) -> list[tuple[bool, str]]:
    doctor = submission.get("assigned_doctor", {}) or {}
    results: list[tuple[bool, str]] = []
    if doctor_email_ready(doctor):
        try:
            results.append(send_submission_email(submission, file_attachments=file_attachments))
        except Exception as exc:
            results.append((False, f"Email не отправлен: {exc}"))
    elif smtp_configured():
        results.append(
            (
                False,
                "Email: у врача не указан адрес. Заполните email в карточке врача или ANAMNES_SMTP_TO.",
            )
        )
    if doctor_telegram_ready(doctor):
        try:
            results.append(send_telegram_notification(submission))
        except Exception as exc:
            results.append((False, f"Telegram не отправлен: {exc}"))
    return results
