from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def session_dir() -> Path:
    base = Path(os.getenv("ANAMNES_DATA_DIR", "data"))
    path = base / "telegram_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_path(chat_id: int) -> Path:
    return session_dir() / f"{chat_id}.json"


def load_session(chat_id: int) -> dict[str, Any] | None:
    path = session_path(chat_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def save_session(session: dict[str, Any]) -> None:
    chat_id = int(session["chat_id"])
    session_path(chat_id).write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session(chat_id: int) -> None:
    path = session_path(chat_id)
    if path.exists():
        path.unlink()


def new_session(chat_id: int, doctor_id: str) -> dict[str, Any]:
    return {
        "chat_id": chat_id,
        "doctor_id": doctor_id,
        "screen": "intro",
        "multi_field": "",
        "multi_selected": [],
        "data": {},
        "pending_files": [],
    }


def step_data(session: dict[str, Any], step_key: str) -> dict[str, Any]:
    data = session.setdefault("data", {})
    block = data.get(step_key)
    if not isinstance(block, dict):
        block = {}
        data[step_key] = block
    return block
