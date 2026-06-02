from __future__ import annotations

from typing import Any

from .models import MAIN_REASONS, Submission

REASON_LABELS = dict(MAIN_REASONS)


def _step(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "не указано"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "не указано"
    return str(value)


def reason_labels(data: dict[str, Any]) -> str:
    step2 = _step(data, "step2")
    reasons = step2.get("main_reasons") or []
    if not isinstance(reasons, list):
        return "не указано"
    return ", ".join(REASON_LABELS.get(code, code) for code in reasons) or "не указано"


def patient_name(data: dict[str, Any]) -> str:
    return str(_step(data, "step1").get("full_name") or "Без имени")


def build_submission_summary(submission: Submission) -> str:
    data = submission.data if isinstance(submission.data, dict) else {}
    step1 = _step(data, "step1")
    step3 = _step(data, "step3")
    step4 = _step(data, "step4")

    lines = [
        "КРАТКО",
        f"Пациент: {_fmt(step1.get('full_name'))}, {_fmt(step1.get('age'))} лет.",
        f"Причина обращения: {reason_labels(data)}.",
        f"Жалобы: {_fmt(step3.get('complaints'))}.",
        "",
        "ПАЦИЕНТ",
        f"- Телефон: {_fmt(step1.get('phone'))}",
        f"- Город: {_fmt(step1.get('city'))}",
        f"- Пол: {_fmt(step1.get('sex'))}",
        f"- Рост/вес: {_fmt(step1.get('height_cm'))} см / {_fmt(step1.get('weight_kg'))} кг",
        "",
        "ОБЩИЙ АНАМНЕЗ",
        f"- Хронические заболевания: {_fmt(step3.get('chronic_conditions'))}",
        f"- Лекарства: {_fmt(step3.get('medications'))}",
        f"- Аллергии: {_fmt(step3.get('allergy_status'))}",
        "",
        "КОММЕНТАРИЙ ПАЦИЕНТА",
        _fmt(step4.get("additional_comment")),
    ]
    return "\n".join(lines)
