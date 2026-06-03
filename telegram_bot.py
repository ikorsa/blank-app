import os
import sys
import time
import traceback

from telegram_intake.api import (
    TelegramNetworkError,
    api_request,
    poll_updates,
    safe_answer_callback,
    send_message,
)
from telegram_intake.choices import preload_wizard_choices, wizard_choices_error
from telegram_intake.doctors import get_doctor, load_doctors
from telegram_intake.picker import doctors_picker_keyboard
from telegram_intake.session import ensure_session_storage, load_session
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


def parse_start_payload(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    payload = parts[1].strip().lower()
    if payload.startswith("doctor_"):
        payload = payload[len("doctor_") :]
    return payload


def send_doctor_picker(chat_id: int, doctors: list[dict[str, str]], *, title: str) -> None:
    if not doctors:
        send_message(chat_id, "Список врачей пока не настроен.")
        return
    text = (
        f"{title}\n\n"
        "Нажмите на врача ниже или откройте персональную ссылку от клиники.\n"
        f"Пример: t.me/{BOT_USERNAME}?start=doctor_{doctors[0]['id']}"
    )
    send_message(chat_id, text, doctors_picker_keyboard(doctors))


def _chat_id_from_message(message: dict) -> int | None:
    chat = message.get("chat") or {}
    raw = chat.get("id")
    return int(raw) if raw is not None else None


def handle_command(message: dict) -> None:
    chat_id = _chat_id_from_message(message)
    text = str(message.get("text") or "").strip()
    if chat_id is None:
        return

    doctors = load_doctors()

    if text.startswith("/start"):
        doctor_id = parse_start_payload(text)
        doctor = get_doctor(doctor_id) if doctor_id else None
        if doctor:
            start_wizard_for_doctor(chat_id, doctor)
            return
        if doctor_id:
            send_message(chat_id, f"Врач с кодом '{doctor_id}' не найден. Проверьте ссылку или /doctors.")
            return
        if len(doctors) == 1:
            start_wizard_for_doctor(chat_id, doctors[0])
            return
        send_doctor_picker(
            chat_id,
            doctors,
            title="Здравствуйте! Выберите врача для анкеты перед приёмом:",
        )
        return

    if text.startswith("/doctors"):
        send_doctor_picker(chat_id, doctors, title="Доступные врачи:")
        return

    if text.startswith("/help"):
        send_message(
            chat_id,
            "Как заполнить анкету:\n\n"
            f"1. /start или /doctors — выберите врача кнопкой\n"
            f"2. Или ссылка t.me/{BOT_USERNAME}?start=doctor_КОД\n"
            "3. «Заполнить в Telegram» — пошагово в боте\n"
            "4. Или «Открыть на сайте» — в браузере\n"
            "5. В конце — «Отправить врачу»\n\n"
            "Команды:\n"
            "/doctors — список врачей\n"
            "/cancel — отменить текущую анкету\n"
            "/web — ссылка на сайт (во время заполнения)",
        )
        return

    if load_session(chat_id):
        handle_text(message)
        return

    send_message(
        chat_id,
        f"Помогу заполнить анкету перед приёмом.\n"
        f"Начните: /start или /doctors\n"
        f"Бот: @{BOT_USERNAME}",
    )


def handle_doctor_pick(callback: dict) -> bool:
    data = str(callback.get("data") or "")
    if not data.startswith("doc:"):
        return False
    doctor_id = data.split(":", 1)[1].strip().lower()
    message = callback.get("message") or {}
    chat_id = _chat_id_from_message(message)
    callback_id = str(callback.get("id") or "")
    if chat_id is None:
        return True
    doctor = get_doctor(doctor_id)
    if not doctor:
        safe_answer_callback(callback_id)
        send_message(chat_id, f"Врач «{doctor_id}» не найден. Попробуйте /doctors.")
        return True
    safe_answer_callback(callback_id)
    try:
        start_wizard_for_doctor(chat_id, doctor)
    except Exception as exc:
        print(f"Doctor pick failed ({doctor_id}): {exc}", flush=True)
        print(traceback.format_exc(), flush=True)
        from telegram_intake.wizard import intake_url

        send_message(
            chat_id,
            "Не удалось начать анкету.\n"
            f"Откройте на сайте: {intake_url(doctor_id)}\n"
            "Или попробуйте /start снова.",
        )
    return True


def handle_update(update: dict) -> None:
    callback = update.get("callback_query")
    if callback:
        if handle_doctor_pick(callback):
            return
        try:
            handle_callback(callback, get_doctor)
        except TelegramNetworkError as exc:
            print(f"Callback network error: {exc}", flush=True)
            return
        except Exception as exc:
            print(f"Callback handler error: {exc}", flush=True)
            print(traceback.format_exc(), flush=True)
            message = callback.get("message") or {}
            chat_id = _chat_id_from_message(message)
            if chat_id is not None:
                session = load_session(chat_id)
                doctor_id = str((session or {}).get("doctor_id") or "").strip()
                from telegram_intake.wizard import intake_url

                site = intake_url(doctor_id) if doctor_id else "https://anamnes.ikorsakov.tech/"
                try:
                    send_message(
                        chat_id,
                        "Не удалось продолжить анкету.\n"
                        f"Откройте на сайте: {site}\n"
                        "Или попробуйте /start или /doctors.",
                    )
                except TelegramNetworkError:
                    pass
            return
        message = callback.get("message") or {}
        chat_id = _chat_id_from_message(message)
        data = str(callback.get("data") or "")
        if chat_id is not None and data.endswith(":done") and data.startswith("s2"):
            session = load_session(chat_id)
            if session and session.get("screen") == "s2_reasons" and not session.get("multi_selected"):
                send_message(chat_id, "Выберите хотя бы одну причину обращения.")
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
    network_backoff = 5
    while True:
        try:
            updates, offset = poll_updates(offset)
            network_backoff = 5
            for update in updates:
                try:
                    handle_update(update)
                except TelegramNetworkError as exc:
                    print(f"Update handler network error: {exc}", flush=True)
                except Exception as exc:
                    print(f"Update handler error: {exc}", flush=True)
                    print(traceback.format_exc(), flush=True)
                    message = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
                    chat_id = _chat_id_from_message(message)
                    if chat_id is not None:
                        try:
                            send_message(chat_id, "Произошла ошибка. Попробуйте /start или /doctors.")
                        except TelegramNetworkError:
                            pass
                        except Exception:
                            pass
        except TelegramNetworkError as exc:
            print(f"Telegram poll network error (retry in {network_backoff}s): {exc}", flush=True)
            time.sleep(network_backoff)
            network_backoff = min(network_backoff * 2, 60)
        except Exception as exc:
            print(f"Telegram bot error: {exc}", flush=True)
            time.sleep(network_backoff)
            network_backoff = min(network_backoff * 2, 60)


if __name__ == "__main__":
    if not os.getenv("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN", ""):
        raise SystemExit("Set ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN before starting the bot.")
    print(f"Telegram bot python: {sys.executable}", flush=True)
    try:
        storage = ensure_session_storage()
        print(f"Telegram session storage: {storage}", flush=True)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    ensure_polling_mode()
    if preload_wizard_choices():
        print("Wizard choices loaded.", flush=True)
    else:
        detail = wizard_choices_error() or "unknown error"
        print(
            f"WARNING: wizard choices not loaded ({detail}). "
            "«Заполнить в Telegram» will show a site link until Django is fixed.",
            flush=True,
        )
    print("Telegram patient bot: polling started (wizard enabled).", flush=True)
    poll_forever()
