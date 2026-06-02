from __future__ import annotations

from typing import Any

from .branch_fields import REASON_LABELS, format_branch_key
from .forms import REPRODUCTIVE_STATUS_CHOICES, URGENT_SYMPTOM_CHOICES
from .models import MAIN_REASONS, Submission

REASON_LABELS.update(dict(MAIN_REASONS))

REPRODUCTIVE_LABELS = dict(REPRODUCTIVE_STATUS_CHOICES)
URGENT_LABELS = dict(URGENT_SYMPTOM_CHOICES)

SEX_LABELS = {"female": "Женский", "male": "Мужской"}


def _step(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "не указано"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "не указано"
    return str(value)


def _calculate_bmi(height_cm: Any, weight_kg: Any) -> float | None:
    try:
        height = float(height_cm)
        weight = float(weight_kg)
    except (TypeError, ValueError):
        return None
    if height <= 0:
        return None
    height_m = height / 100
    return round(weight / (height_m * height_m), 1)


def reason_labels(data: dict[str, Any]) -> str:
    step2 = _step(data, "step2")
    reasons = step2.get("main_reasons") or []
    if not isinstance(reasons, list):
        return "не указано"
    return ", ".join(REASON_LABELS.get(code, code) for code in reasons) or "не указано"


def patient_name(data: dict[str, Any]) -> str:
    return str(_step(data, "step1").get("full_name") or "Без имени")


def _files_step(data: dict[str, Any]) -> dict[str, Any]:
    step5 = _step(data, "step5")
    if step5:
        return step5
    step4 = _step(data, "step4")
    if "additional_comment" in step4:
        return step4
    return {}


def _branch_step(data: dict[str, Any]) -> dict[str, Any]:
    step4 = _step(data, "step4")
    if "additional_comment" in step4:
        return {}
    return step4


def build_submission_summary(data: dict[str, Any]) -> str:
    step1 = _step(data, "step1")
    step3 = _step(data, "step3")
    step5 = _files_step(data)
    branches = _branch_step(data)

    bmi = _calculate_bmi(step1.get("height_cm"), step1.get("weight_kg"))
    sex_label = SEX_LABELS.get(str(step1.get("sex")), _fmt(step1.get("sex")))
    reproductive = REPRODUCTIVE_LABELS.get(str(step1.get("reproductive_status", "")), "")
    urgent = step1.get("urgent_symptoms") or []
    urgent_text = [URGENT_LABELS.get(str(item), str(item)) for item in urgent] if isinstance(urgent, list) else []

    lines = [
        "КРАТКО",
        f"Пациент: {_fmt(step1.get('full_name'))}, {_fmt(step1.get('age'))} лет, {sex_label.lower()}, "
        f"ИМТ {bmi if bmi is not None else 'не рассчитан'}.",
        f"Причина обращения: {reason_labels(data)}.",
        f"Ключевые жалобы: {_fmt(step3.get('complaints'))}.",
        "",
        "КРАСНЫЕ ФЛАГИ",
    ]
    if urgent_text:
        lines.append("ВНИМАНИЕ: пациент отметил потенциально срочные симптомы:")
        lines.extend([f"- {item}" for item in urgent_text])
    else:
        lines.append("Не отмечены.")

    lines.extend(
        [
            "",
            "ПАЦИЕНТ",
            f"- Телефон: {_fmt(step1.get('phone'))}",
            f"- Город: {_fmt(step1.get('city'))}",
            f"- Пол: {sex_label}",
            f"- Возраст: {_fmt(step1.get('age'))}",
            f"- Рост/вес: {_fmt(step1.get('height_cm'))} см / {_fmt(step1.get('weight_kg'))} кг",
            f"- ИМТ: {bmi if bmi is not None else 'не рассчитан'}",
            f"- Беременность/лактация: {reproductive or 'не указано'}",
            "",
            "ОБЩИЙ АНАМНЕЗ",
            f"- Когда появились жалобы: {_fmt(step3.get('complaints_started'))}",
            f"- Хронические заболевания: {_fmt(step3.get('chronic_conditions'))}",
            f"- Уточнение по хроническим заболеваниям: {_fmt(step3.get('chronic_conditions_other'))}",
            f"- Операции: {_fmt(step3.get('surgeries'))}",
            f"- Постоянные лекарства: {_fmt(step3.get('medications'))}",
            f"- Уточнение по лекарствам: {_fmt(step3.get('medications_details'))}",
            f"- Аллергии на лекарства: {_fmt(step3.get('allergy_status'))}",
            f"- Уточнение по аллергиям: {_fmt(step3.get('allergies_details'))}",
            f"- Семейный анамнез: {_fmt(step3.get('family_history'))}",
            f"- Обычное АД: {_fmt(step3.get('blood_pressure'))}",
            f"- Курение: {_fmt(step3.get('smoking'))}",
            "",
            "ПРОФИЛЬНЫЕ БЛОКИ",
        ]
    )

    if branches:
        for reason, answers in branches.items():
            lines.append(f"{REASON_LABELS.get(reason, reason)}:")
            if isinstance(answers, dict):
                for key, value in answers.items():
                    lines.append(f"- {format_branch_key(key)}: {_fmt(value)}")
            else:
                lines.append(f"- {_fmt(answers)}")
            lines.append("")
    else:
        lines.append("Не заполнены.")

    lines.extend(
        [
            "ФАЙЛЫ И КОММЕНТАРИИ",
            f"- Комментарий пациента: {_fmt(step5.get('additional_comment'))}",
        ]
    )
    return "\n".join(lines)


def build_submission_summary_from_model(submission: Submission) -> str:
    data = submission.data if isinstance(submission.data, dict) else {}
    return build_submission_summary(data)
