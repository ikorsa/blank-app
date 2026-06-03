from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

from . import api
from .branches import (
    advance_branch,
    branch_callback_prefix,
    branch_step4_block,
    current_branch_item,
    init_branch_flow,
    save_branch_value,
)
from .choices import wizard_choices
from .session import clear_session, load_session, new_session, save_session, step_data
from .submit import submit_session

PUBLIC_URL = os.getenv("ANAMNES_PUBLIC_URL", "https://anamnes.ikorsakov.tech").rstrip("/")

TEXT_REPLY_HINT = (
    "\n\n✏️ Напишите ответ обычным сообщением в поле «Сообщение» внизу экрана и нажмите отправить."
)

SCREEN_PROGRESS = {
    "s1_full_name": (1, "Контакты"),
    "s1_age": (1, "Контакты"),
    "s1_sex": (1, "Контакты"),
    "s1_phone": (1, "Контакты"),
    "s1_city": (1, "Контакты"),
    "s1_height": (1, "Контакты"),
    "s1_weight": (1, "Контакты"),
    "s1_reproductive": (1, "Контакты"),
    "s1_urgent": (1, "Контакты"),
    "s2_reasons": (2, "Причина"),
    "s3_complaints": (3, "Анамнез"),
    "s3_complaints_started": (3, "Анамнез"),
    "s3_chronic": (3, "Анамнез"),
    "s3_surgeries": (3, "Анамнез"),
    "s3_medications": (3, "Анамнез"),
    "s3_medications_details": (3, "Анамнез"),
    "s3_allergy": (3, "Анамнез"),
    "s3_allergies_details": (3, "Анамнез"),
    "s3_family": (3, "Анамнез"),
    "s3_bp": (3, "Анамнез"),
    "s3_smoking": (3, "Анамнез"),
    "s4_branch": (4, "Профиль"),
    "s5_files": (5, "Файлы"),
    "s5_comment": (5, "Файлы"),
    "s6_confirm": (6, "Отправка"),
}


def intake_url(doctor_id: str) -> str:
    return f"{PUBLIC_URL}/?doctor={quote(doctor_id)}"


def progress_line(screen: str) -> str:
    info = SCREEN_PROGRESS.get(screen)
    if not info:
        return ""
    step_num, label = info
    return f"Шаг {step_num} из 6 · {label}\n\n"


def choice_keyboard(prefix: str, choices: list[tuple[str, str]]) -> dict[str, Any]:
    rows = [[{"text": label, "callback_data": f"{prefix}:{code}"}] for code, label in choices if code]
    return {"inline_keyboard": rows}


def multi_keyboard(prefix: str, choices: list[tuple[str, str]], selected: list[str]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    selected_set = set(selected)
    for code, label in choices:
        if code in selected_set:
            button_text = f"✅ {label}"
        else:
            button_text = f"☐ {label}"
        rows.append([{"text": button_text, "callback_data": f"{prefix}:t:{code}"}])
    done_count = len(selected_set)
    done_label = f"Готово ({done_count}) →" if done_count else "Готово →"
    rows.append([{"text": done_label, "callback_data": f"{prefix}:done"}])
    return {"inline_keyboard": rows}


def _resolved_multi_selected(session: dict[str, Any], field_key: str, stored: Any) -> list[str]:
    """Keep in-progress toggles; load from saved data only when opening the field."""
    if session.get("multi_field") == field_key:
        return [str(item) for item in (session.get("multi_selected") or [])]
    if isinstance(stored, list):
        return [str(item) for item in stored]
    return []


def _prepare_multi(session: dict[str, Any], field_key: str, stored: Any) -> list[str]:
    selected = _resolved_multi_selected(session, field_key, stored)
    _start_multi(session, field_key, selected)
    return selected


def intro_keyboard(doctor_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "Заполнить в Telegram", "callback_data": "wiz:start"}],
            [{"text": "Открыть на сайте", "url": intake_url(doctor_id)}],
        ]
    }


def nav_keyboard(*, back: str | None = None, skip: bool = False) -> dict[str, Any] | None:
    row: list[dict[str, str]] = []
    if back:
        row.append({"text": "← Назад", "callback_data": f"nav:back:{back}"})
    if skip:
        row.append({"text": "Пропустить →", "callback_data": "nav:skip"})
    row.append({"text": "Отмена", "callback_data": "nav:cancel"})
    return {"inline_keyboard": [row]} if row else None


def _set_screen(session: dict[str, Any], screen: str) -> None:
    session["screen"] = screen
    session["multi_field"] = ""
    session["multi_selected"] = []
    save_session(session)


def _start_multi(session: dict[str, Any], field_key: str, selected: list[str] | None = None) -> None:
    session["multi_field"] = field_key
    session["multi_selected"] = list(selected or [])


def _doctor_label(doctor: dict[str, str]) -> str:
    return f"{doctor.get('name', doctor.get('id'))} ({doctor.get('specialty', 'Эндокринолог')})"


def send_intro(chat_id: int, doctor: dict[str, str]) -> None:
    doctor_id = str(doctor.get("id") or "").strip()
    if not doctor_id:
        raise RuntimeError("Doctor id is missing")
    text = (
        f"Здравствуйте!\n\n"
        f"Анкета перед приёмом эндокринолога (10–15 минут).\n\n"
        f"Врач: {_doctor_label(doctor)}\n\n"
        "• Можно заполнить здесь в Telegram или на сайте\n"
        "• Не заменяет скорую помощь при острых симптомах\n\n"
        "Выберите способ:"
    )
    api.send_message(chat_id, text, intro_keyboard(doctor_id))


def _append_skip_profile_row(markup: dict[str, Any] | None) -> dict[str, Any] | None:
    if not markup:
        markup = {"inline_keyboard": []}
    rows = list(markup.get("inline_keyboard") or [])
    rows.append([{"text": "Пропустить профиль →", "callback_data": "s4:skip"}])
    markup["inline_keyboard"] = rows
    return markup


def prompt_for_screen(session: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    screen = session["screen"]
    choices = wizard_choices()
    markup: dict[str, Any] | None = None
    prefix = progress_line(screen)

    if screen == "s1_full_name":
        text = prefix + "Как вас зовут? (ФИО)" + TEXT_REPLY_HINT
        markup = nav_keyboard(skip=False)
    elif screen == "s1_age":
        text = prefix + "Сколько вам полных лет?" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s1_full_name")
    elif screen == "s1_sex":
        text = prefix + "Укажите пол:"
        markup = choice_keyboard("s1_sex", choices["sex"])
    elif screen == "s1_phone":
        text = prefix + "Телефон для связи (например +7 900 000-00-00):" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s1_age")
    elif screen == "s1_city":
        text = prefix + "Город проживания:" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s1_phone")
    elif screen == "s1_height":
        text = prefix + "Рост в см (например 170):" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s1_city")
    elif screen == "s1_weight":
        text = prefix + "Вес в кг (например 72.5):" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s1_height")
    elif screen == "s1_reproductive":
        text = prefix + "Беременность / лактация:"
        markup = choice_keyboard("s1_repro", choices["reproductive"])
    elif screen == "s1_urgent":
        text = prefix + "Отметьте срочные симптомы, если есть сейчас (можно ничего не выбирать):"
        field_key = "step1.urgent_symptoms"
        selected = _prepare_multi(session, field_key, step_data(session, "step1").get("urgent_symptoms"))
        markup = multi_keyboard("s1_urg", choices["urgent"], selected)
    elif screen == "s2_reasons":
        text = prefix + "Причина обращения (можно несколько):"
        field_key = "step2.main_reasons"
        selected = _prepare_multi(session, field_key, step_data(session, "step2").get("main_reasons"))
        markup = multi_keyboard("s2", choices["reasons"], selected)
    elif screen == "s3_complaints":
        text = prefix + "Какие жалобы беспокоят сейчас? (своими словами)" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s2_reasons", skip=True)
    elif screen == "s3_complaints_started":
        text = prefix + "Когда появились жалобы?"
        markup = choice_keyboard("s3_start", choices["complaints_started"])
    elif screen == "s3_chronic":
        text = prefix + "Хронические заболевания (можно несколько):"
        field_key = "step3.chronic_conditions"
        selected = _prepare_multi(session, field_key, step_data(session, "step3").get("chronic_conditions"))
        markup = multi_keyboard("s3_chron", choices["chronic_conditions"], selected)
    elif screen == "s3_surgeries":
        text = prefix + "Были ли операции? (кратко или «нет»)" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s3_chronic", skip=True)
    elif screen == "s3_medications":
        text = prefix + "Постоянные лекарства (можно несколько):"
        field_key = "step3.medications"
        selected = _prepare_multi(session, field_key, step_data(session, "step3").get("medications"))
        markup = multi_keyboard("s3_med", choices["medications"], selected)
    elif screen == "s3_medications_details":
        text = prefix + "Уточните названия, дозировки и режим приёма:" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s3_medications", skip=True)
    elif screen == "s3_allergy":
        text = prefix + "Есть ли аллергии на лекарства?"
        markup = choice_keyboard("s3_allergy", choices["allergy_status"])
    elif screen == "s3_allergies_details":
        text = prefix + "На какие лекарства и какая реакция?" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s3_allergy", skip=True)
    elif screen == "s3_family":
        text = prefix + "Эндокринные заболевания у родственников:"
        field_key = "step3.family_history"
        selected = _prepare_multi(session, field_key, step_data(session, "step3").get("family_history"))
        markup = multi_keyboard("s3_fam", choices["family_history"], selected)
    elif screen == "s3_bp":
        text = prefix + "Ваше обычное артериальное давление?" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s3_family", skip=True)
    elif screen == "s3_smoking":
        text = prefix + "Курите?"
        markup = choice_keyboard("s3_smoke", choices["smoking"])
    elif screen == "s4_branch":
        item = current_branch_item(session)
        if not item:
            _set_screen(session, "s5_files")
            return prompt_for_screen(session)
        index = int(session.get("branch_index") or 0)
        total = len(session.get("branch_queue") or [])
        text = prefix + f"{item['reason_label']} ({index + 1}/{total})\n\n{item['label']}"
        if item.get("kind") == "text":
            text += TEXT_REPLY_HINT
        prefix_key = branch_callback_prefix(item)
        if item["kind"] == "choice":
            markup = choice_keyboard(f"{prefix_key}:c", item["choices"])
        elif item["kind"] == "multi":
            field_key = f"step4|{item['reason']}|{item['field_name']}"
            block = branch_step4_block(session, item["reason"])
            selected = _prepare_multi(session, field_key, block.get(item["field_name"]))
            markup = multi_keyboard(prefix_key, item["choices"], selected)
        else:
            markup = nav_keyboard(skip=True)
        markup = _append_skip_profile_row(markup)
    elif screen == "s5_files":
        count = len(session.get("pending_files") or [])
        text = (
            prefix
            + f"Пришлите фото или PDF анализов (до 10 файлов). Уже загружено: {count}.\n"
            + "Когда закончите — нажмите «Далее»."
        )
        markup = {
            "inline_keyboard": [
                [{"text": "Далее →", "callback_data": "s5:next"}],
                [{"text": "Пропустить файлы", "callback_data": "s5:skip"}],
            ]
        }
    elif screen == "s5_comment":
        text = prefix + "Комментарий для врача (необязательно):" + TEXT_REPLY_HINT
        markup = nav_keyboard(back="s5_files", skip=True)
    elif screen == "s6_confirm":
        from .django_bootstrap import ensure_django

        ensure_django()
        from intake.summary import build_submission_summary

        summary = build_submission_summary(session.get("data") or {})
        if len(summary) > 3500:
            summary = summary[:3500] + "\n… (полный текст в письме врачу)"
        text = prefix + "Проверьте данные перед отправкой:\n\n" + summary
        markup = {
            "inline_keyboard": [
                [{"text": "✅ Отправить врачу", "callback_data": "s6:submit"}],
                [{"text": "← Назад", "callback_data": "nav:back:s5_comment"}],
                [{"text": "Отмена", "callback_data": "nav:cancel"}],
            ]
        }
    else:
        text = "Продолжаем анкету…"
    return text, markup


def _multi_field_for_prefix(prefix: str) -> str:
    return {
        "s1_urg": "step1.urgent_symptoms",
        "s2": "step2.main_reasons",
        "s3_chron": "step3.chronic_conditions",
        "s3_med": "step3.medications",
        "s3_fam": "step3.family_history",
    }.get(prefix, "")


def _ensure_multi_field(session: dict[str, Any], prefix: str) -> None:
    field_key = _multi_field_for_prefix(prefix)
    if field_key:
        session["multi_field"] = field_key


def send_screen(chat_id: int, session: dict[str, Any]) -> None:
    text, markup = prompt_for_screen(session)
    save_session(session)
    api.send_message(chat_id, text, markup)


def _validate_age(text: str) -> int | None:
    try:
        age = int(text.strip())
    except ValueError:
        return None
    return age if 1 <= age <= 120 else None


def _validate_int(text: str, low: int, high: int) -> int | None:
    try:
        value = int(text.strip())
    except ValueError:
        return None
    return value if low <= value <= high else None


def _validate_weight(text: str) -> float | None:
    cleaned = text.strip().replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 0.1 <= value <= 500 else None


def _save_multi(session: dict[str, Any]) -> None:
    field_key = session.get("multi_field") or ""
    if field_key.startswith("step4|"):
        parts = field_key.split("|", 2)
        if len(parts) == 3:
            _, reason, field_name = parts
            save_branch_value(session, reason, field_name, list(session.get("multi_selected") or []))
        return
    if not field_key or "." not in field_key:
        return
    step_key, field_name = field_key.split(".", 1)
    step_data(session, step_key)[field_name] = list(session.get("multi_selected") or [])


def _apply_choice(session: dict[str, Any], step_key: str, field: str, code: str) -> None:
    step_data(session, step_key)[field] = code


def handle_cancel(chat_id: int) -> None:
    clear_session(chat_id)
    api.send_message(chat_id, "Анкета отменена. Чтобы начать снова — /start doctor_КОД")


def handle_callback(callback: dict[str, Any], doctor_lookup) -> None:
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    data = str(callback.get("data") or "")
    callback_id = str(callback.get("id") or "")
    if not chat_id:
        return

    session = load_session(int(chat_id))
    if not session and data == "wiz:start":
        api.safe_answer_callback(callback_id, "Сначала /start doctor_КОД")
        return
    if not session:
        api.safe_answer_callback(callback_id)
        return

    if (":t:" in data or data.endswith(":done")) and data.endswith(":done"):
        prefix = data.rsplit(":done", 1)[0]
        if prefix == "s2" and not session.get("multi_selected"):
            api.safe_answer_callback(callback_id, "Выберите хотя бы одну причину обращения.")
            return

    api.safe_answer_callback(callback_id)

    if data == "wiz:start":
        _set_screen(session, "s1_full_name")
        send_screen(int(chat_id), session)
        return

    if data == "nav:cancel":
        handle_cancel(int(chat_id))
        return

    if data == "nav:skip":
        _advance_after_skip(session)
        save_session(session)
        send_screen(int(chat_id), session)
        return

    if data.startswith("nav:back:"):
        back_screen = data.split(":", 2)[2]
        _set_screen(session, back_screen)
        send_screen(int(chat_id), session)
        return

    if data == "s4:skip":
        session["branch_queue"] = []
        session["branch_index"] = 0
        _set_screen(session, "s5_files")
        send_screen(int(chat_id), session)
        return

    if ":c:" in data and data.startswith("b4:"):
        left, code = data.split(":c:", 1)
        parts = left.split(":")
        if len(parts) >= 3:
            reason, field_name = parts[1], parts[2]
            save_branch_value(session, reason, field_name, code)
            _set_screen(session, advance_branch(session))
            save_session(session)
            send_screen(int(chat_id), session)
        return

    if data in {"s5:next", "s5:skip"}:
        step_data(session, "step5")
        _set_screen(session, "s5_comment")
        send_screen(int(chat_id), session)
        return

    if data == "s6:submit":
        try:
            submission_id, notify_results = submit_session(session)
        except Exception as exc:
            api.send_message(int(chat_id), f"Не удалось отправить анкету: {exc}")
            return
        lines = [f"✅ Анкета отправлена.\n\nНомер: `{submission_id}`"]
        for ok, note in notify_results:
            lines.append(("✓ " if ok else "⚠ ") + note)
        lines.append("\nСпасибо! Врач получит данные.")
        api.send_message(int(chat_id), "\n".join(lines))
        return

    if ":t:" in data or data.endswith(":done"):
        prior_screen = session["screen"]
        _handle_multi_callback(session, data)
        save_session(session)
        if session["screen"] != prior_screen:
            send_screen(int(chat_id), session)
            return
        message_id = message.get("message_id")
        if message_id:
            text, markup = prompt_for_screen(session)
            if api.try_edit_message(int(chat_id), int(message_id), text, markup):
                save_session(session)
                return
            if markup and api.try_edit_reply_markup(int(chat_id), int(message_id), markup):
                save_session(session)
                return
        send_screen(int(chat_id), session)
        return

    _handle_single_choice(session, data)
    save_session(session)
    send_screen(int(chat_id), session)


def _handle_multi_callback(session: dict[str, Any], data: str) -> None:
    session["_last_multi_screen"] = session["screen"]
    if data.endswith(":done"):
        prefix = data.rsplit(":done", 1)[0]
        _ensure_multi_field(session, prefix)
        _save_multi(session)
        if session.get("screen") == "s4_branch":
            _set_screen(session, advance_branch(session))
            return
        _advance_after_multi(session, prefix)
        return
    match = re.match(r"^(.+):t:(.+)$", data)
    if not match:
        return
    prefix, code = match.group(1), match.group(2)
    _ensure_multi_field(session, prefix)
    selected = list(session.get("multi_selected") or [])
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    session["multi_selected"] = selected


def _handle_single_choice(session: dict[str, Any], data: str) -> None:
    if data.startswith("s1_sex:"):
        _apply_choice(session, "step1", "sex", data.split(":", 1)[1])
        _set_screen(session, "s1_phone")
    elif data.startswith("s1_repro:"):
        _apply_choice(session, "step1", "reproductive_status", data.split(":", 1)[1])
        _set_screen(session, "s1_urgent")
    elif data.startswith("s3_start:"):
        _apply_choice(session, "step3", "complaints_started", data.split(":", 1)[1])
        _set_screen(session, "s3_chronic")
    elif data.startswith("s3_allergy:"):
        code = data.split(":", 1)[1]
        _apply_choice(session, "step3", "allergy_status", code)
        _set_screen(session, "s3_allergies_details" if code == "yes" else "s3_family")
    elif data.startswith("s3_smoke:"):
        _apply_choice(session, "step3", "smoking", data.split(":", 1)[1])
        _set_screen(session, init_branch_flow(session))


def _advance_after_multi(session: dict[str, Any], prefix: str) -> None:
    if prefix == "s2" and not session.get("multi_selected"):
        session["screen"] = "s2_reasons"
        session["_last_multi_screen"] = "s2_reasons"
        return
    mapping = {
        "s1_urg": "s2_reasons",
        "s2": "s3_complaints",
        "s3_chron": "s3_surgeries",
        "s3_med": "s3_medications_details",
        "s3_fam": "s3_bp",
    }
    next_screen = mapping.get(prefix, session["screen"])
    _set_screen(session, next_screen)


def _advance_after_skip(session: dict[str, Any]) -> None:
    screen = session["screen"]
    if screen == "s3_complaints":
        step_data(session, "step3")["complaints"] = ""
    elif screen == "s3_surgeries":
        step_data(session, "step3")["surgeries"] = ""
    elif screen == "s3_medications_details":
        step_data(session, "step3")["medications_details"] = ""
    elif screen == "s3_allergies_details":
        step_data(session, "step3")["allergies_details"] = ""
    elif screen == "s3_bp":
        step_data(session, "step3")["blood_pressure"] = ""
    elif screen == "s4_branch":
        item = current_branch_item(session)
        if item:
            save_branch_value(session, str(item["reason"]), str(item["field_name"]), "")
        _set_screen(session, advance_branch(session))
        return
    elif screen == "s5_comment":
        step_data(session, "step5")["additional_comment"] = ""
        _set_screen(session, "s6_confirm")
        return

    next_map = {
        "s3_complaints": "s3_complaints_started",
        "s3_surgeries": "s3_medications",
        "s3_medications_details": "s3_allergy",
        "s3_allergies_details": "s3_family",
        "s3_bp": "s3_smoking",
    }
    _set_screen(session, next_map.get(screen, "s6_confirm"))


def handle_text(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if not chat_id:
        return

    if text.startswith("/cancel"):
        handle_cancel(int(chat_id))
        return

    session = load_session(int(chat_id))
    if not session:
        return

    if text.startswith("/web"):
        api.send_message(int(chat_id), f"Ссылка на анкету:\n{intake_url(session['doctor_id'])}")
        return

    screen = session["screen"]
    s1 = step_data(session, "step1")
    s3 = step_data(session, "step3")
    s5 = step_data(session, "step5")

    if screen == "s1_full_name":
        if len(text) < 2:
            api.send_message(int(chat_id), "Укажите ФИО полностью.")
            return
        s1["full_name"] = text
        _set_screen(session, "s1_age")
    elif screen == "s1_age":
        age = _validate_age(text)
        if age is None:
            api.send_message(int(chat_id), "Введите возраст числом от 1 до 120.")
            return
        s1["age"] = age
        _set_screen(session, "s1_sex")
    elif screen == "s1_phone":
        s1["phone"] = text
        _set_screen(session, "s1_city")
    elif screen == "s1_city":
        s1["city"] = text
        _set_screen(session, "s1_height")
    elif screen == "s1_height":
        height = _validate_int(text, 50, 250)
        if height is None:
            api.send_message(int(chat_id), "Рост — число от 50 до 250 см.")
            return
        s1["height_cm"] = height
        _set_screen(session, "s1_weight")
    elif screen == "s1_weight":
        weight = _validate_weight(text)
        if weight is None:
            api.send_message(int(chat_id), "Вес — число, например 72.5")
            return
        s1["weight_kg"] = weight
        _set_screen(session, "s1_reproductive")
    elif screen == "s3_complaints":
        s3["complaints"] = text
        _set_screen(session, "s3_complaints_started")
    elif screen == "s3_surgeries":
        s3["surgeries"] = text
        _set_screen(session, "s3_medications")
    elif screen == "s3_medications_details":
        s3["medications_details"] = text
        _set_screen(session, "s3_allergy")
    elif screen == "s3_allergies_details":
        s3["allergies_details"] = text
        _set_screen(session, "s3_family")
    elif screen == "s3_bp":
        s3["blood_pressure"] = text
        _set_screen(session, "s3_smoking")
    elif screen == "s4_branch":
        item = current_branch_item(session)
        if not item or item.get("kind") != "text":
            api.send_message(int(chat_id), "Используйте кнопки на экране или «Пропустить».")
            return
        save_branch_value(session, str(item["reason"]), str(item["field_name"]), text)
        _set_screen(session, advance_branch(session))
    elif screen == "s5_comment":
        s5["additional_comment"] = text
        _set_screen(session, "s6_confirm")
    else:
        api.send_message(
            int(chat_id),
            "На этом шаге нужно написать ответ сообщением внизу экрана (поле «Сообщение»). "
            "Или используйте кнопки на экране. /cancel — отмена.",
        )
        return

    save_session(session)
    send_screen(int(chat_id), session)


def handle_file(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return
    session = load_session(int(chat_id))
    if not session or session.get("screen") != "s5_files":
        api.send_message(int(chat_id), "Файлы можно прикрепить на шаге «Файлы» во время заполнения анкеты.")
        return

    pending = session.setdefault("pending_files", [])
    if len(pending) >= 10:
        api.send_message(int(chat_id), "Максимум 10 файлов. Нажмите «Далее».")
        return

    file_id = ""
    original_name = "file"
    if message.get("document"):
        doc = message["document"]
        file_id = doc.get("file_id", "")
        original_name = doc.get("file_name") or "document"
    elif message.get("photo"):
        photo = message["photo"][-1]
        file_id = photo.get("file_id", "")
        original_name = f"photo_{len(pending) + 1}.jpg"

    if not file_id:
        return

    pending.append({"telegram_file_id": file_id, "original_name": original_name})
    save_session(session)
    api.send_message(
        int(chat_id),
        f"Файл принят ({original_name}). Всего: {len(pending)}. Можете отправить ещё или нажать «Далее».",
    )


def start_wizard_for_doctor(chat_id: int, doctor: dict[str, str]) -> None:
    session = new_session(chat_id, doctor["id"])
    session["screen"] = "intro"
    save_session(session)
    send_intro(chat_id, doctor)
