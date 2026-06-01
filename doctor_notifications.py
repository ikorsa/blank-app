"""Email and Telegram notifications to doctors on new submissions."""

from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
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


def send_submission_email(submission: dict[str, Any]) -> tuple[bool, str]:
    doctor = submission.get("assigned_doctor", {}) or {}
    recipient = str(doctor.get("email") or "").strip() or SMTP_TO
    if not smtp_configured():
        return False, "SMTP не настроен: задайте ANAMNES_SMTP_* в окружении."
    if not recipient:
        return False, "Нет email врача и не задан ANAMNES_SMTP_TO."

    patient = submission.get("patient", {})
    reason = ", ".join(submission.get("main_reasons") or []) or "—"
    subject = f"Новая анкета эндокринолога: {patient.get('full_name', 'без имени')}"
    body = (
        "Получена новая анкета пациента.\n\n"
        f"Пациент: {format_answer(patient.get('full_name'))}\n"
        f"Телефон: {format_answer(patient.get('phone'))}\n"
        f"Причина обращения: {reason}\n"
        f"ID анкеты: {submission['id']}\n"
        f"Дата UTC: {submission.get('created_at', '')}\n\n"
        "Резюме:\n"
        f"{submission.get('summary', '')}\n\n"
        "Загруженные файлы — в кабинете врача на сайте.\n"
        f"Кабинет: {PUBLIC_URL}\n"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = recipient
    message.set_content(body)
    message.add_attachment(
        json.dumps(submission, ensure_ascii=False, indent=2).encode("utf-8"),
        maintype="application",
        subtype="json",
        filename=f"submission_{submission['id']}.json",
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)

    return True, f"Копия анкеты отправлена на {recipient}."


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


def notify_doctor_on_submission(submission: dict[str, Any]) -> list[tuple[bool, str]]:
    doctor = submission.get("assigned_doctor", {}) or {}
    results: list[tuple[bool, str]] = []
    if doctor_email_ready(doctor):
        try:
            results.append(send_submission_email(submission))
        except Exception as exc:
            results.append((False, f"Email не отправлен: {exc}"))
    if doctor_telegram_ready(doctor):
        try:
            results.append(send_telegram_notification(submission))
        except Exception as exc:
            results.append((False, f"Telegram не отправлен: {exc}"))
    return results
