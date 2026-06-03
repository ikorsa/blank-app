from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def session_dir() -> Path:
    base = Path(os.getenv("ANAMNES_DATA_DIR", "data"))
    path = base / "telegram_sessions"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Cannot create telegram session dir {path}: {exc}") from exc
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
    path = session_path(chat_id)
    try:
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Cannot write telegram session {path}: {exc}") from exc


def ensure_session_storage() -> Path:
    """Verify bot can write wizard sessions (call on startup)."""
    directory = session_dir()
    probe = directory / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Telegram session dir not writable: {directory} ({exc})") from exc
    return directory


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
