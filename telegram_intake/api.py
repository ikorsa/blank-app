from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BOT_TOKEN = os.getenv("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN", "")
POLL_TIMEOUT = int(os.getenv("ANAMNES_TELEGRAM_POLL_TIMEOUT", "30"))
REQUEST_TIMEOUT = int(os.getenv("ANAMNES_TELEGRAM_REQUEST_TIMEOUT", "30"))
POLL_HTTP_TIMEOUT = POLL_TIMEOUT + int(os.getenv("ANAMNES_TELEGRAM_POLL_GRACE", "25"))


class TelegramNetworkError(RuntimeError):
    """Telegram Bot API call failed due to network/connectivity."""


def _prepare_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(payload)
    if "chat_id" in prepared and prepared["chat_id"] is not None:
        prepared["chat_id"] = int(prepared["chat_id"])
    if "message_id" in prepared and prepared["message_id"] is not None:
        prepared["message_id"] = int(prepared["message_id"])
    return prepared


def api_request(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    http_timeout: int | None = None,
) -> dict[str, Any]:
    if not BOT_TOKEN:
        raise RuntimeError("ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN is not set")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(_prepare_payload(payload), ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    timeout = REQUEST_TIMEOUT if http_timeout is None else http_timeout
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API {method} HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise TelegramNetworkError(f"Telegram API {method} network error: {reason}") from exc
    except TimeoutError as exc:
        raise TelegramNetworkError(f"Telegram API {method} timed out after {timeout}s") from exc

    if not body.get("ok", True):
        raise RuntimeError(f"Telegram API {method} failed: {body}")
    return body


def send_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> int | None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = api_request("sendMessage", payload)
    message = result.get("result") or {}
    return message.get("message_id")


def edit_message(chat_id: int, message_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api_request("editMessageText", payload)


def answer_callback(callback_query_id: str | int, text: str = "") -> None:
    query_id = str(callback_query_id).strip()
    if not query_id:
        return
    payload: dict[str, Any] = {"callback_query_id": query_id}
    if text:
        payload["text"] = text[:200]
    api_request("answerCallbackQuery", payload)


def safe_answer_callback(callback_query_id: str | int, text: str = "") -> None:
    try:
        answer_callback(callback_query_id, text)
    except Exception as exc:
        message = str(exc).lower()
        if "query is too old" in message or "query id is invalid" in message:
            return
        print(f"answerCallbackQuery warning: {exc}", flush=True)


def download_file(file_id: str) -> tuple[bytes, str]:
    meta = api_request("getFile", {"file_id": file_id})
    file_path = str((meta.get("result") or {}).get("file_path") or "")
    if not file_path:
        raise RuntimeError("Telegram getFile returned empty path")
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT + 30) as response:
            content = response.read()
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise TelegramNetworkError(f"Telegram file download network error: {reason}") from exc
    name = file_path.rsplit("/", 1)[-1]
    return content, name


def poll_updates(offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    query = urlencode({"timeout": POLL_TIMEOUT, "offset": offset})
    response = api_request(f"getUpdates?{query}", http_timeout=POLL_HTTP_TIMEOUT)
    updates = response.get("result") or []
    new_offset = offset
    for update in updates:
        new_offset = max(new_offset, int(update.get("update_id", 0)) + 1)
    return updates, new_offset
