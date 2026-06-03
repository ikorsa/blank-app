import os
import time

from telegram_intake.api import api_request, poll_updates, send_message
from telegram_intake.doctors import get_doctor, load_doctors
from telegram_intake.session import load_session
from telegram_intake.wizard import (
    handle_callback,
    handle_file,
    handle_text,
    start_wizard_for_doctor,
)

BOT_USERNAME = os.getenv("ANAMNES_TELEGRAM_BOT_USERNAME", "ikorsakov_anamnes_bot").lstrip("@")


def _load_local_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


def doctor_label(doctor: dict[str, str]) -> str:
    return f"{doctor['name']} ({doctor['specialty']})"


def parse_start_payload(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    payload = parts[1].strip().lower()
    if payload.startswith("doctor_"):
        payload = payload[len("doctor_") :]
    return payload


def handle_command(message: dict) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if not chat_id:
        return

    doctors = load_doctors()

    if text.startswith("/start"):
        doctor_id = parse_start_payload(text)
        doctor = get_doctor(doctor_id) if doctor_id else None
        if doctor:
            start_wizard_for_doctor(int(chat_id), doctor)
            return
        if doctor_id:
            send_message(chat_id, f"Врач с кодом '{doctor_id}' не найден. Проверьте ссылку или /doctors.")
            return
        if len(doctors) == 1:
            start_wizard_for_doctor(int(chat_id), doctors[0])
            return
        send_message(
            chat_id,
            "Здравствуйте. Откройте персональную ссылку врача или команду /doctors.",
        )
        return

    if text.startswith("/doctors"):
        if not doctors:
            send_message(chat_id, "Список врачей пока не настроен.")
            return
        lines = ["Доступные врачи:"]
        for doctor in doctors:
            lines.append(f"- {doctor_label(doctor)}: /start doctor_{doctor['id']}")
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/help"):
        send_message(
            chat_id,
            "Как заполнить анкету:\n\n"
            f"1. Откройте ссылку t.me/{BOT_USERNAME}?start=doctor_КОД\n"
            "2. «Заполнить в Telegram» — пошагово в боте\n"
            "3. Или «Открыть на сайте» — в браузере\n"
            "4. В конце — «Отправить врачу»\n\n"
            "Команды:\n"
            "/doctors — список врачей\n"
            "/cancel — отменить текущую анкету\n"
            "/web — ссылка на сайт (во время заполнения)",
        )
        return

    if load_session(int(chat_id)):
        handle_text(message)
        return

    send_message(
        chat_id,
        f"Помогу заполнить анкету перед приёмом.\n"
        f"Начните: /start doctor_КОД или /help\n"
        f"Бот: @{BOT_USERNAME}",
    )


def handle_update(update: dict) -> None:
    callback = update.get("callback_query")
    if callback:
        handle_callback(callback, get_doctor)
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        data = str(callback.get("data") or "")
        if chat_id and data.endswith(":done") and data.startswith("s2"):
            session = load_session(int(chat_id))
            if session and session.get("screen") == "s2_reasons" and not session.get("multi_selected"):
                send_message(int(chat_id), "Выберите хотя бы одну причину обращения.")
        return

    message = update.get("message")
    if not message:
        return

    if message.get("text"):
        handle_command(message)
        return

    if message.get("photo") or message.get("document"):
        handle_file(message)


def ensure_polling_mode() -> None:
    try:
        api_request("deleteWebhook", {"drop_pending_updates": False})
    except Exception as exc:
        print(f"Warning: deleteWebhook failed: {exc}", flush=True)


def poll_forever() -> None:
    offset = 0
    while True:
        try:
            updates, offset = poll_updates(offset)
            for update in updates:
                handle_update(update)
        except Exception as exc:
            print(f"Telegram bot error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    if not os.getenv("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN", ""):
        raise SystemExit("Set ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN before starting the bot.")
    ensure_polling_mode()
    print("Telegram patient bot: polling started (wizard enabled).", flush=True)
    poll_forever()
