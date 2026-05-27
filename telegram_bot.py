import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DATA_DIR = Path(os.getenv("ANAMNES_DATA_DIR", "data"))
DOCTORS_FILE = Path(os.getenv("ANAMNES_DOCTORS_FILE", str(DATA_DIR / "doctors.json")))
PUBLIC_URL = os.getenv("ANAMNES_PUBLIC_URL", "https://anamnes.ikorsakov.tech").rstrip("/")
BOT_TOKEN = os.getenv("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN", "")
POLL_TIMEOUT = int(os.getenv("ANAMNES_TELEGRAM_POLL_TIMEOUT", "30"))


def normalize_doctor(doctor: dict[str, Any]) -> dict[str, str]:
    doctor_id = str(doctor.get("id") or doctor.get("slug") or "").strip().lower()
    return {
        "id": doctor_id,
        "name": str(doctor.get("name") or doctor_id or "Врач"),
        "specialty": str(doctor.get("specialty") or "Эндокринолог"),
    }


def load_doctors() -> list[dict[str, str]]:
    if not DOCTORS_FILE.exists():
        return [
            {
                "id": "default",
                "name": "Врач по умолчанию",
                "specialty": "Эндокринолог",
            }
        ]
    try:
        raw = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    items = raw.get("doctors", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    doctors = [normalize_doctor(item) for item in items if isinstance(item, dict)]
    return [doctor for doctor in doctors if doctor["id"]]


def get_doctor(doctors: list[dict[str, str]], doctor_id: str) -> dict[str, str] | None:
    return next((doctor for doctor in doctors if doctor["id"] == doctor_id), None)


def doctor_label(doctor: dict[str, str]) -> str:
    return f"{doctor['name']} ({doctor['specialty']})"


def intake_url(doctor_id: str) -> str:
    return f"{PUBLIC_URL}/?doctor={quote(doctor_id)}"


def api_request(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN is not set")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urlopen(request, timeout=POLL_TIMEOUT + 10) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api_request("sendMessage", payload)


def send_doctor_link(chat_id: int, doctor: dict[str, str]) -> None:
    url = intake_url(doctor["id"])
    text = (
        "Анкета перед приемом эндокринолога.\n\n"
        f"Врач: {doctor_label(doctor)}\n\n"
        "Нажмите кнопку ниже, чтобы заполнить анкету. Можно вернуться к ссылке позже."
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "Заполнить анкету", "url": url}],
        ]
    }
    send_message(chat_id, text, keyboard)


def parse_start_payload(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    payload = parts[1].strip().lower()
    if payload.startswith("doctor_"):
        payload = payload[len("doctor_") :]
    return payload


def handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if not chat_id:
        return

    doctors = load_doctors()
    if text.startswith("/start"):
        doctor_id = parse_start_payload(text)
        doctor = get_doctor(doctors, doctor_id) if doctor_id else None
        if doctor:
            send_doctor_link(chat_id, doctor)
            return
        if doctor_id:
            send_message(chat_id, f"Врач с кодом '{doctor_id}' не найден. Проверьте ссылку или выберите из списка /doctors.")
            return
        if len(doctors) == 1:
            send_doctor_link(chat_id, doctors[0])
            return
        send_message(chat_id, "Здравствуйте. Чтобы получить ссылку на анкету, откройте персональную ссылку врача или команду /doctors.")
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
            "Откройте персональную ссылку врача вида:\n"
            "t.me/<bot>?start=doctor_ivanova\n\n"
            "Или используйте /doctors для списка врачей.",
        )
        return

    send_message(chat_id, "Я помогу открыть анкету перед приемом. Используйте /help или персональную ссылку врача.")


def poll_updates() -> None:
    offset = 0
    while True:
        query = urlencode({"timeout": POLL_TIMEOUT, "offset": offset})
        try:
            response = api_request(f"getUpdates?{query}")
            for update in response.get("result", []):
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                message = update.get("message")
                if message:
                    handle_message(message)
        except Exception as exc:
            print(f"Telegram bot error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("Set ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN before starting the bot.")
    poll_updates()
