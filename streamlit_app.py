import json
import os
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


APP_TITLE = "Анамнез эндокринолога"
DATA_DIR = Path(os.getenv("ANAMNES_DATA_DIR", "data"))
SUBMISSIONS_DIR = DATA_DIR / "submissions"
UPLOADS_DIR = DATA_DIR / "uploads"
DOCTORS_FILE = Path(os.getenv("ANAMNES_DOCTORS_FILE", str(DATA_DIR / "doctors.json")))
ADMIN_PASSWORD = os.getenv("ANAMNES_ADMIN_PASSWORD", "admin")
SMTP_HOST = os.getenv("ANAMNES_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("ANAMNES_SMTP_PORT", "587"))
SMTP_USER = os.getenv("ANAMNES_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("ANAMNES_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("ANAMNES_SMTP_FROM", SMTP_USER)
SMTP_TO = os.getenv("ANAMNES_SMTP_TO", "")
PDF_FONT_NAME = "DejaVuSans"
PUBLIC_URL = os.getenv("ANAMNES_PUBLIC_URL", "https://anamnes.ikorsakov.tech")
TELEGRAM_BOT_TOKEN = os.getenv("ANAMNES_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("ANAMNES_TELEGRAM_CHAT_ID", "")

MAIN_REASONS = {
    "thyroid": "Щитовидная железа",
    "diabetes": "Сахарный диабет / высокий сахар",
    "weight": "Лишний вес / ожирение",
    "hormones": "Нарушение цикла / гормоны / бесплодие",
    "fatigue": "Усталость / слабость / выпадение волос",
    "bone": "Остеопороз / витамин D / кальций",
    "other": "Другое",
}

NO_URGENT_SYMPTOMS = "Нет"
URGENT_SYMPTOMS = [
    NO_URGENT_SYMPTOMS,
    "Потеря сознания",
    "Сильная одышка",
    "Боль в груди",
    "Сахар выше 20 ммоль/л",
    "Рвота и выраженная слабость при диабете",
    "Спутанность сознания",
]

SUBMISSION_STATUSES = {
    "submitted": "Новая",
    "in_progress": "В работе",
    "viewed": "Просмотрена",
    "closed": "Закрыта",
}


def init_storage() -> None:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def default_doctor() -> dict[str, str]:
    return {
        "id": "default",
        "name": "Врач по умолчанию",
        "specialty": "Эндокринолог",
        "email": SMTP_TO,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
        "password": ADMIN_PASSWORD,
    }


def normalize_doctor(doctor: dict[str, Any]) -> dict[str, str]:
    doctor_id = safe_filename(str(doctor.get("id") or doctor.get("slug") or "")).lower()
    return {
        "id": doctor_id,
        "name": str(doctor.get("name") or doctor_id or "Врач"),
        "specialty": str(doctor.get("specialty") or "Эндокринолог"),
        "email": str(doctor.get("email") or ""),
        "telegram_chat_id": str(doctor.get("telegram_chat_id") or ""),
        "password": str(doctor.get("password") or ""),
    }


def load_doctors() -> list[dict[str, str]]:
    if not DOCTORS_FILE.exists():
        return [default_doctor()]
    try:
        raw = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [default_doctor()]

    items = raw.get("doctors", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return [default_doctor()]

    doctors = [normalize_doctor(item) for item in items if isinstance(item, dict)]
    doctors = [doctor for doctor in doctors if doctor["id"] and doctor["name"]]
    return doctors or [default_doctor()]


def public_doctor_info(doctor: dict[str, str] | None) -> dict[str, str]:
    if not doctor:
        return {"id": "", "name": "Не выбран", "specialty": "", "email": "", "telegram_chat_id": ""}
    return {
        "id": doctor.get("id", ""),
        "name": doctor.get("name", ""),
        "specialty": doctor.get("specialty", ""),
        "email": doctor.get("email", ""),
        "telegram_chat_id": doctor.get("telegram_chat_id", ""),
    }


def get_query_param(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def get_doctor_by_id(doctors: list[dict[str, str]], doctor_id: str) -> dict[str, str] | None:
    return next((doctor for doctor in doctors if doctor["id"] == doctor_id), None)


def doctor_display_name(doctor: dict[str, str] | None) -> str:
    if not doctor:
        return "Врач не выбран"
    specialty = doctor.get("specialty") or "Врач"
    return f"{doctor.get('name', 'Врач')} ({specialty})"


def resolve_patient_doctor(doctors: list[dict[str, str]]) -> dict[str, str]:
    doctor_id = get_query_param("doctor").strip().lower()
    doctor = get_doctor_by_id(doctors, doctor_id) if doctor_id else None
    if doctor:
        return doctor

    if doctor_id:
        st.warning(f"Врач с кодом '{doctor_id}' не найден. Выберите врача из списка.")

    if len(doctors) == 1:
        return doctors[0]

    selected_id = st.selectbox(
        "Выберите врача",
        [doctor["id"] for doctor in doctors],
        format_func=lambda item: doctor_display_name(get_doctor_by_id(doctors, item)),
        key="patient_doctor_select",
    )
    return get_doctor_by_id(doctors, selected_id) or doctors[0]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9._-]+", "_", name).strip("._")
    return cleaned or "file"


def format_answer(value: Any) -> str:
    if value is None or value == "":
        return "не указано"
    if isinstance(value, list):
        return ", ".join(value) if value else "не указано"
    return str(value)


def get_submission_reason_values(submission: dict[str, Any]) -> list[str]:
    reasons = submission.get("main_reasons")
    return reasons if isinstance(reasons, list) else []


def get_submission_reason_labels(submission: dict[str, Any]) -> list[str]:
    return [MAIN_REASONS.get(reason, reason) for reason in get_submission_reason_values(submission)]


def format_submission_reasons(submission: dict[str, Any]) -> str:
    return ", ".join(get_submission_reason_labels(submission)) or "не указано"


def get_red_flags(submission: dict[str, Any]) -> list[str]:
    return [item for item in submission.get("urgent_symptoms", []) if item != NO_URGENT_SYMPTOMS]


def format_branch_key(key: str) -> str:
    labels = {
        "diagnosis": "Диагноз",
        "medications": "Препараты",
        "medications_details": "Уточнение по препаратам",
        "insulin": "Инсулин",
        "insulin_types": "Типы инсулина",
        "insulin_regimen": "Режим инсулинотерапии",
        "insulin_daily_units": "Дозы/схема инсулина",
        "first_detected": "Когда выявлено",
        "fasting_glucose": "Сахар натощак",
        "post_meal_glucose": "Сахар после еды",
        "hba1c": "HbA1c",
        "hypoglycemia": "Гипогликемии",
        "complications": "Осложнения/жалобы",
        "dose": "Доза/длительность приема",
        "last_lab_date": "Дата последних анализов",
        "last_tsh_date": "Дата последнего ТТГ",
        "last_tsh_value": "ТТГ",
        "free_t4_value": "Т4 свободный",
        "free_t3_value": "Т3 свободный",
        "antibodies": "Антитела",
        "ultrasound": "УЗИ",
        "ultrasound_findings": "Находки УЗИ",
        "symptoms": "Симптомы",
        "waist_cm": "Окружность талии",
        "weight_gain_started": "Когда начался набор веса",
        "weight_gain_amount": "Набор веса за период",
        "max_weight": "Максимальный вес",
        "appetite": "Аппетит",
        "previous_attempts": "Попытки снижения веса",
        "weight_loss_result": "Результат снижения веса",
        "night_eating": "Ночные перекусы",
        "snoring": "Храп/апноэ",
        "sleep_duration": "Сон",
        "physical_activity": "Физическая активность",
        "hypertension": "Повышенное давление",
        "weight_gain_medications": "Лекарства, связанные с набором веса",
        "metabolic_tests": "Сахар/инсулин/HbA1c",
        "details": "Описание",
        "expectations": "Ожидания от консультации",
    }
    return labels.get(key, key.replace("_", " "))


def calculate_bmi(height_cm: int | None, weight_kg: float | None) -> float | None:
    if not height_cm or not weight_kg:
        return None
    height_m = height_cm / 100
    if height_m <= 0:
        return None
    return round(weight_kg / (height_m * height_m), 1)


def register_pdf_font() -> str:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        if Path(font_path).exists():
            if PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, font_path))
            return PDF_FONT_NAME
    return "Helvetica"


def build_summary_pdf(summary: str, title: str) -> bytes:
    buffer = BytesIO()
    font_name = register_pdf_font()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "AnamnesNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )
    heading = ParagraphStyle(
        "AnamnesHeading",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=14,
        leading=18,
        spaceAfter=8,
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story = [Paragraph(title, heading), Spacer(1, 4 * mm)]
    for line in summary.splitlines():
        text = line if line.strip() else "&nbsp;"
        story.append(Paragraph(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), normal))
    doc.build(story)
    return buffer.getvalue()


def selectbox_from_map(label: str, options: dict[str, str], key: str) -> str:
    values = list(options.keys())
    selected = st.selectbox(label, values, format_func=lambda item: options[item], key=key)
    return selected


def render_common_questions() -> dict[str, Any]:
    st.subheader("Общий анамнез")
    chronic_conditions = st.multiselect(
        "Какие хронические заболевания есть?",
        [
            "Нет хронических заболеваний",
            "Артериальная гипертония",
            "Сахарный диабет",
            "Заболевания щитовидной железы",
            "Ишемическая болезнь сердца / стенокардия",
            "Аритмия",
            "Инфаркт или инсульт в прошлом",
            "Хронические заболевания почек",
            "Хронические заболевания печени",
            "Заболевания желудка/кишечника",
            "Бронхиальная астма / ХОБЛ",
            "Аутоиммунные заболевания",
            "Онкологические заболевания",
            "Остеопороз",
            "Депрессия / тревожное расстройство",
            "Не знаю",
            "Другое",
        ],
        key="common_chronic",
    )
    chronic_conditions_other = ""
    if "Другое" in chronic_conditions:
        chronic_conditions_other = st.text_input("Уточните хронические заболевания", key="common_chronic_other")

    medications = st.multiselect(
        "Какие лекарства принимаете постоянно?",
        [
            "Не принимаю постоянно",
            "Препараты от давления",
            "Препараты от сахара",
            "Инсулин",
            "L-тироксин / Эутирокс",
            "Тирозол / пропицил",
            "Статины / препараты холестерина",
            "Антикоагулянты / антиагреганты",
            "Мочегонные",
            "Гормональные препараты / контрацептивы",
            "Антидепрессанты / противотревожные",
            "Глюкокортикоиды",
            "Витамин D / кальций",
            "БАДы",
            "Не помню",
            "Другое",
        ],
        key="common_medications_select",
    )
    medications_details = st.text_area(
        "Уточните названия, дозировки и режим приема лекарств",
        key="common_medications_details",
    )

    allergy_status = st.selectbox(
        "Есть ли аллергии на лекарства?",
        ["Нет", "Да", "Не знаю"],
        key="common_allergy_status",
    )
    allergies_details = ""
    if allergy_status == "Да":
        allergies_details = st.text_area("На какие лекарства и какая реакция?", key="common_allergies_details")

    return {
        "complaints": st.text_area("Какие жалобы беспокоят сейчас?", key="common_complaints"),
        "complaints_started": st.selectbox(
            "Когда появились жалобы?",
            [
                "Менее недели назад",
                "1-4 недели назад",
                "1-6 месяцев назад",
                "Более 6 месяцев назад",
                "Затрудняюсь ответить",
            ],
            key="common_complaints_started",
        ),
        "chronic_conditions": chronic_conditions,
        "chronic_conditions_other": chronic_conditions_other,
        "surgeries": st.text_area("Были ли операции?", key="common_surgeries"),
        "medications": medications,
        "medications_details": medications_details,
        "allergy_status": allergy_status,
        "allergies_details": allergies_details,
        "family_history": st.multiselect(
            "Есть ли у родственников эндокринные заболевания?",
            ["Диабет", "Болезни щитовидной железы", "Ожирение", "Остеопороз", "Не знаю", "Нет"],
            key="common_family_history",
        ),
        "blood_pressure": st.text_input("Ваше обычное артериальное давление?", key="common_bp"),
        "smoking": st.selectbox("Курите?", ["Нет", "Да", "Бросил/бросила"], key="common_smoking"),
    }


def render_thyroid_branch() -> dict[str, Any]:
    st.subheader("Ветка: щитовидная железа")
    return {
        "diagnosis": st.multiselect(
            "Есть ли установленный диагноз?",
            [
                "Гипотиреоз",
                "АИТ / аутоиммунный тиреоидит",
                "Узлы щитовидной железы",
                "Тиреотоксикоз / гипертиреоз",
                "После операции на щитовидной железе",
                "Диагноза нет",
                "Не знаю",
            ],
            key="thyroid_diagnosis",
        ),
        "medications": st.multiselect(
            "Принимаете ли препараты для щитовидной железы?",
            [
                "Не принимаю",
                "Эутирокс",
                "L-тироксин",
                "Тирозол",
                "Пропицил",
                "Йод",
                "Селен",
                "Не помню",
                "Другое",
            ],
            key="thyroid_medications",
        ),
        "dose": st.text_input("Укажите дозировку и как давно принимаете", key="thyroid_dose"),
        "last_lab_date": st.text_input("Дата последних анализов щитовидной железы", key="thyroid_last_lab_date"),
        "last_tsh_date": st.selectbox(
            "Когда последний раз сдавали ТТГ?",
            ["Менее 1 месяца назад", "1-3 месяца назад", "3-6 месяцев назад", "Более 6 месяцев назад", "Не сдавал/не помню"],
            key="thyroid_last_tsh_date",
        ),
        "last_tsh_value": st.text_input("Укажите результат ТТГ, если помните", key="thyroid_last_tsh_value"),
        "free_t4_value": st.text_input("Т4 свободный, если помните", key="thyroid_free_t4"),
        "free_t3_value": st.text_input("Т3 свободный, если помните", key="thyroid_free_t3"),
        "antibodies": st.multiselect(
            "Сдавали ли антитела?",
            ["АТ-ТПО", "АТ-ТГ", "Антитела к рецептору ТТГ", "Не сдавал/не помню"],
            key="thyroid_antibodies",
        ),
        "ultrasound": st.selectbox(
            "Есть ли УЗИ щитовидной железы?",
            ["Да, могу загрузить", "Да, но нет с собой", "Нет"],
            key="thyroid_ultrasound",
        ),
        "ultrasound_findings": st.multiselect(
            "Что было на УЗИ, если известно?",
            ["Узлы", "Кисты", "Увеличение железы", "Уменьшение железы", "Признаки тиреоидита", "Не знаю"],
            key="thyroid_ultrasound_findings",
        ),
        "symptoms": st.multiselect(
            "Какие симптомы есть?",
            [
                "Сердцебиение",
                "Дрожь в руках",
                "Потливость",
                "Раздражительность",
                "Сонливость",
                "Отеки",
                "Выпадение волос",
                "Сухость кожи",
                "Изменение веса",
                "Ком в горле",
                "Ничего из перечисленного",
            ],
            key="thyroid_symptoms",
        ),
    }


def render_diabetes_branch() -> dict[str, Any]:
    st.subheader("Ветка: сахарный диабет / высокий сахар")
    insulin = st.selectbox("Используете ли инсулин?", ["Нет", "Да"], key="diabetes_insulin")
    glucose_medications = st.multiselect(
        "Какие препараты принимаете от сахара?",
        [
            "Не принимаю",
            "Метформин",
            "Сульфонилмочевина: гликлазид / Диабетон / глимепирид / Амарил",
            "Ингибиторы ДПП-4: ситаглиптин / вилдаглиптин / линаглиптин",
            "Ингибиторы SGLT2: дапаглифлозин / эмпаглифлозин / канаглифлозин",
            "Агонисты ГПП-1: семаглутид / лираглутид / дулаглутид",
            "Тиазолидиндионы: пиоглитазон",
            "Акарбоза",
            "Инсулин короткого действия",
            "Инсулин длительного действия",
            "Комбинированный инсулин",
            "Не помню",
            "Другое",
        ],
        key="diabetes_medications",
    )
    glucose_medications_details = st.text_area(
        "Уточните названия, дозировки и режим приема препаратов от сахара",
        key="diabetes_medications_details",
    )
    data = {
        "diagnosis": st.selectbox(
            "Есть ли диагноз сахарного диабета?",
            [
                "Диабет 1 типа",
                "Диабет 2 типа",
                "Предиабет",
                "Гестационный диабет был раньше",
                "Диагноза нет, но повышен сахар",
                "Не знаю",
            ],
            key="diabetes_diagnosis",
        ),
        "first_detected": st.text_input("Когда впервые выявили повышение сахара/диабет?", key="diabetes_first_detected"),
        "medications": glucose_medications,
        "medications_details": glucose_medications_details,
        "insulin": insulin,
        "fasting_glucose": st.text_input("Какой сахар обычно натощак?", key="diabetes_fasting_glucose"),
        "post_meal_glucose": st.text_input("Какой сахар обычно после еды?", key="diabetes_post_meal_glucose"),
        "hba1c": st.text_input("Последний HbA1c, если знаете", key="diabetes_hba1c"),
        "hypoglycemia": st.selectbox(
            "Бывают ли гипогликемии: дрожь, пот, слабость, низкий сахар?",
            ["Нет", "Иногда", "Да, часто", "Не измеряю"],
            key="diabetes_hypoglycemia",
        ),
        "complications": st.multiselect(
            "Есть ли осложнения или жалобы?",
            [
                "Ухудшение зрения",
                "Онемение/жжение в ногах",
                "Проблемы с почками",
                "Раны плохо заживают",
                "Боли в сердце/сосудах",
                "Ничего из перечисленного",
            ],
            key="diabetes_complications",
        ),
    }
    if insulin == "Да":
        data["insulin_types"] = st.multiselect(
            "Какой инсулин используете?",
            [
                "Ультракороткий: НовоРапид / Хумалог / Апидра / Фиасп",
                "Короткий: Актрапид / Хумулин Регуляр",
                "Средней продолжительности: Протафан / НПХ",
                "Длительный: Лантус / Левемир / Туджео / Тресиба",
                "Смешанный: НовоМикс / Хумалог Микс / Хумулин М3",
                "Помпа",
                "Не помню",
                "Другое",
            ],
            key="diabetes_insulin_types",
        )
        data["insulin_regimen"] = st.multiselect(
            "Какой режим инсулинотерапии?",
            [
                "1 раз в день",
                "2 раза в день",
                "Перед каждым приемом пищи",
                "Базис-болюсная схема",
                "Коррекция по сахару",
                "Инсулиновая помпа",
                "Не знаю",
                "Другое",
            ],
            key="diabetes_insulin_regimen",
        )
        data["insulin_daily_units"] = st.text_input(
            "Сколько единиц в сутки или по какой схеме?",
            key="diabetes_insulin_daily_units",
        )
    return data


def render_weight_branch() -> dict[str, Any]:
    st.subheader("Ветка: лишний вес / ожирение")
    return {
        "waist_cm": st.text_input("Окружность талии, см, если знаете", key="weight_waist_cm"),
        "weight_gain_started": st.selectbox(
            "Когда начался набор веса?",
            ["С детства", "После 18 лет", "После беременности", "После стресса", "После начала лекарств", "В последние месяцы", "Не знаю"],
            key="weight_gain_started",
        ),
        "weight_gain_amount": st.text_input("Сколько кг набрали и за какой период?", key="weight_gain_amount"),
        "max_weight": st.text_input("Максимальный вес в жизни?", key="weight_max_weight"),
        "appetite": st.selectbox("Как изменился аппетит?", ["Не изменился", "Повышен", "Снижен", "Приступы сильного голода", "Не знаю"], key="weight_appetite"),
        "previous_attempts": st.multiselect(
            "Были ли попытки снижения веса?",
            ["Диета", "Спорт", "Лекарства", "Операция", "Нет"],
            key="weight_previous_attempts",
        ),
        "weight_loss_result": st.selectbox(
            "Вес снижался раньше?",
            ["Да, но вернулся", "Да, удерживаю", "Нет", "Не пробовал/не пробовала"],
            key="weight_loss_result",
        ),
        "night_eating": st.selectbox("Есть ли ночные перекусы или переедание вечером?", ["Нет", "Да", "Иногда"], key="weight_night_eating"),
        "snoring": st.selectbox("Есть ли храп или остановки дыхания во сне?", ["Нет", "Да", "Не знаю"], key="weight_snoring"),
        "sleep_duration": st.selectbox("Сколько обычно спите?", ["Менее 5 часов", "5-6 часов", "7-8 часов", "Более 8 часов", "Не знаю"], key="weight_sleep_duration"),
        "physical_activity": st.selectbox(
            "Физическая активность",
            ["Низкая", "Хожу пешком регулярно", "Тренировки 1-2 раза в неделю", "Тренировки 3+ раза в неделю", "Ограничена из-за здоровья"],
            key="weight_physical_activity",
        ),
        "hypertension": st.selectbox("Есть ли повышенное давление?", ["Нет", "Да", "Не знаю"], key="weight_hypertension"),
        "weight_gain_medications": st.multiselect(
            "Были ли лекарства, после которых мог начаться набор веса?",
            ["Гормоны/глюкокортикоиды", "Антидепрессанты", "Нейролептики", "Инсулин", "Препараты от эпилепсии", "Не было", "Не знаю", "Другое"],
            key="weight_gain_medications",
        ),
        "metabolic_tests": st.selectbox(
            "Сдавали ли сахар, инсулин, HbA1c?",
            ["Да, могу указать/загрузить", "Нет", "Не помню"],
            key="weight_metabolic_tests",
        ),
    }


def render_hormones_branch(sex: str) -> dict[str, Any]:
    st.subheader("Ветка: нарушение цикла / гормоны / бесплодие")
    if sex == "Мужской":
        st.info("Выбран мужской пол. Блок адаптирован под общие гормональные жалобы.")
        return {
            "libido": st.selectbox("Есть ли снижение либидо?", ["Нет", "Да", "Затрудняюсь ответить"], key="hormones_libido"),
            "fertility": st.text_area("Есть ли вопросы по фертильности или гормонам?", key="hormones_fertility"),
            "hormonal_meds": st.text_area("Принимаете ли гормональные препараты?", key="hormones_meds_male"),
        }
    return {
        "cycle_regular": st.selectbox(
            "Регулярный ли менструальный цикл?",
            ["Да", "Нет", "Менопауза", "Беременность", "Не применимо"],
            key="hormones_cycle_regular",
        ),
        "cycle_length": st.text_input("Длительность цикла обычно", key="hormones_cycle_length"),
        "long_delays": st.selectbox("Бывают задержки более 35 дней?", ["Нет", "Да"], key="hormones_long_delays"),
        "acne": st.selectbox("Есть ли акне?", ["Нет", "Да"], key="hormones_acne"),
        "hirsutism": st.selectbox("Есть ли усиленный рост волос на лице/теле?", ["Нет", "Да"], key="hormones_hirsutism"),
        "hair_loss": st.selectbox("Есть ли выпадение волос на голове?", ["Нет", "Да"], key="hormones_hair_loss"),
        "pregnancy_history": st.text_area("Были ли беременности/роды?", key="hormones_pregnancy_history"),
        "pregnancy_plans": st.selectbox("Планируете беременность?", ["Нет", "Да", "Уже беременна"], key="hormones_pregnancy_plans"),
        "hormonal_meds": st.text_area("Принимаете ли гормональные препараты или контрацептивы?", key="hormones_meds"),
    }


def render_fatigue_branch() -> dict[str, Any]:
    st.subheader("Ветка: усталость / слабость / выпадение волос")
    return {
        "main_issue": st.multiselect(
            "Что беспокоит больше всего?",
            ["Слабость", "Сонливость", "Выпадение волос", "Зябкость", "Потливость", "Сердцебиение", "Отечность", "Снижение настроения", "Другое"],
            key="fatigue_main_issue",
        ),
        "duration": st.text_input("Как давно это беспокоит?", key="fatigue_duration"),
        "weight_change": st.selectbox("Изменился ли вес?", ["Не изменился", "Набрал/набрала", "Похудел/похудела"], key="fatigue_weight_change"),
        "sleep": st.selectbox("Какой сон?", ["Нормальный", "Бессонница", "Сонливость днем", "Частые пробуждения"], key="fatigue_sleep"),
        "recent_tests": st.selectbox(
            "Сдавали ли недавно ТТГ, ферритин, витамин D, общий анализ крови?",
            ["Да, могу загрузить", "Нет", "Не помню"],
            key="fatigue_recent_tests",
        ),
    }


def render_bone_branch() -> dict[str, Any]:
    st.subheader("Ветка: остеопороз / витамин D / кальций")
    return {
        "diagnosis": st.selectbox("Был ли диагноз остеопороза/остеопении?", ["Нет", "Да", "Не знаю"], key="bone_diagnosis"),
        "low_trauma_fractures": st.selectbox("Были ли переломы при небольшой травме?", ["Нет", "Да"], key="bone_fractures"),
        "densitometry": st.selectbox("Делали ли денситометрию?", ["Да, могу загрузить", "Нет"], key="bone_densitometry"),
        "supplements": st.text_area("Принимаете ли витамин D или кальций?", key="bone_supplements"),
        "kidney_stones": st.selectbox("Есть ли камни в почках?", ["Нет", "Да", "Не знаю"], key="bone_kidney_stones"),
    }


def render_other_branch() -> dict[str, Any]:
    st.subheader("Ветка: другое")
    return {
        "details": st.text_area("Опишите причину обращения своими словами", key="other_details"),
        "expectations": st.text_area("Что важно получить от консультации?", key="other_expectations"),
    }


def render_branch(reason: str, sex: str) -> dict[str, Any]:
    if reason == "thyroid":
        return render_thyroid_branch()
    if reason == "diabetes":
        return render_diabetes_branch()
    if reason == "weight":
        return render_weight_branch()
    if reason == "hormones":
        return render_hormones_branch(sex)
    if reason == "fatigue":
        return render_fatigue_branch()
    if reason == "bone":
        return render_bone_branch()
    return render_other_branch()


def render_branches(reasons: list[str], sex: str) -> dict[str, Any]:
    branches = {}
    for reason in reasons:
        with st.container(border=True):
            st.markdown(f"### {MAIN_REASONS.get(reason, reason)}")
            branches[reason] = render_branch(reason, sex)
    return branches


def build_summary(submission: dict[str, Any]) -> str:
    patient = submission["patient"]
    assigned_doctor = submission.get("assigned_doctor", {})
    common = submission["common"]
    branch = submission["branch"]
    files = submission["files"]
    bmi = calculate_bmi(patient.get("height_cm"), patient.get("weight_kg"))
    red_flags = get_red_flags(submission)
    patient_intro = (
        f"{format_answer(patient.get('sex')).lower()}, {format_answer(patient.get('age'))} лет, "
        f"ИМТ {bmi if bmi is not None else 'не рассчитан'}"
    )

    lines = [
        "КРАТКО",
        f"{format_answer(patient.get('full_name'))}: {patient_intro}.",
        f"Причина обращения: {format_submission_reasons(submission)}.",
        f"Ключевые жалобы: {format_answer(common.get('complaints'))}.",
        "",
        "КРАСНЫЕ ФЛАГИ",
    ]
    if red_flags:
        lines.append("ВНИМАНИЕ: пациент отметил потенциально срочные симптомы:")
        lines.extend([f"- {item}" for item in red_flags])
    else:
        lines.append("Не отмечены.")

    lines.extend(
        [
            "",
            "ПАЦИЕНТ",
            f"- Врач: {doctor_display_name(assigned_doctor)}",
            f"- Телефон: {format_answer(patient.get('phone'))}",
            f"- Город: {format_answer(patient.get('city'))}",
            f"- Пол: {format_answer(patient.get('sex'))}",
            f"- Возраст: {format_answer(patient.get('age'))}",
            f"- Рост/вес: {format_answer(patient.get('height_cm'))} см / {format_answer(patient.get('weight_kg'))} кг",
            f"- ИМТ: {bmi if bmi is not None else 'не рассчитан'}",
            f"- Беременность/лактация: {format_answer(patient.get('reproductive_status'))}",
            "",
            "ОБЩИЙ АНАМНЕЗ",
            f"- Когда появились жалобы: {format_answer(common.get('complaints_started'))}",
            f"- Хронические заболевания: {format_answer(common.get('chronic_conditions'))}",
            f"- Уточнение по хроническим заболеваниям: {format_answer(common.get('chronic_conditions_other'))}",
            f"- Операции: {format_answer(common.get('surgeries'))}",
            f"- Постоянные лекарства: {format_answer(common.get('medications'))}",
            f"- Уточнение по лекарствам: {format_answer(common.get('medications_details'))}",
            f"- Аллергии на лекарства: {format_answer(common.get('allergy_status'))}",
            f"- Уточнение по аллергиям: {format_answer(common.get('allergies_details'))}",
            f"- Семейный анамнез: {format_answer(common.get('family_history'))}",
            f"- Обычное АД: {format_answer(common.get('blood_pressure'))}",
            f"- Курение: {format_answer(common.get('smoking'))}",
            "",
            "ПРОФИЛЬНЫЕ БЛОКИ",
        ]
    )

    if any(reason in MAIN_REASONS for reason in branch):
        for reason, answers in branch.items():
            lines.append(f"{MAIN_REASONS.get(reason, reason)}:")
            if isinstance(answers, dict):
                for key, value in answers.items():
                    lines.append(f"- {format_branch_key(key)}: {format_answer(value)}")
            else:
                lines.append(f"- {format_answer(answers)}")
            lines.append("")
    else:
        for key, value in branch.items():
            lines.append(f"- {format_branch_key(key)}: {format_answer(value)}")

    lines.extend(
        [
            "ФАЙЛЫ И КОММЕНТАРИИ",
            f"- Комментарий пациента: {format_answer(submission.get('additional_comment'))}",
            f"- Загруженные файлы: {len(files)}",
        ]
    )
    for item in files:
        lines.append(f"  - {item['original_name']} ({item['size']} байт)")

    doctor = submission.get("doctor", {})
    if doctor:
        lines.extend(
            [
                "",
                "СЛУЖЕБНЫЕ ЗАМЕТКИ ВРАЧА",
                f"- Статус: {SUBMISSION_STATUSES.get(submission.get('status'), format_answer(submission.get('status')))}",
                f"- Дата приема: {format_answer(doctor.get('appointment_date'))}",
                f"- Что попросить донести: {format_answer(doctor.get('requested_documents'))}",
                f"- Комментарий врача: {format_answer(doctor.get('note'))}",
            ]
        )
    return "\n".join(lines)

def save_submission(submission: dict[str, Any], uploaded_files: list[Any]) -> str:
    init_storage()
    submission_id = submission["id"]
    upload_dir = UPLOADS_DIR / submission_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for uploaded_file in uploaded_files:
        filename = safe_filename(uploaded_file.name)
        path = upload_dir / filename
        counter = 1
        while path.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        data = uploaded_file.getbuffer()
        path.write_bytes(data)
        saved_files.append(
            {
                "original_name": uploaded_file.name,
                "stored_name": path.name,
                "path": str(path),
                "type": uploaded_file.type,
                "size": len(data),
            }
        )

    submission["files"] = saved_files
    submission["summary"] = build_summary(submission)
    (SUBMISSIONS_DIR / f"{submission_id}.json").write_text(
        json.dumps(submission, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return submission_id


def write_submission_record(submission: dict[str, Any]) -> None:
    submission["summary"] = build_summary(submission)
    (SUBMISSIONS_DIR / f"{submission['id']}.json").write_text(
        json.dumps(submission, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def email_notifications_configured() -> bool:
    return all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TO])


def send_submission_email(submission: dict[str, Any]) -> tuple[bool, str]:
    recipient = submission.get("assigned_doctor", {}).get("email") or SMTP_TO
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, recipient]):
        return False, "Email не настроен: задайте SMTP-переменные окружения."

    patient = submission["patient"]
    reason = format_submission_reasons(submission)
    subject = f"Новая анкета эндокринолога: {patient.get('full_name', 'без имени')}"
    body = (
        "Получена новая анкета пациента.\n\n"
        f"Пациент: {format_answer(patient.get('full_name'))}\n"
        f"Телефон: {format_answer(patient.get('phone'))}\n"
        f"Причина обращения: {reason}\n"
        f"ID анкеты: {submission['id']}\n"
        f"Дата UTC: {submission['created_at']}\n\n"
        "Резюме:\n"
        f"{submission.get('summary', '')}\n\n"
        "Загруженные пациентом файлы не прикладываются к письму; они доступны в кабинете врача."
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


def telegram_notifications_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram_notification(submission: dict[str, Any]) -> tuple[bool, str]:
    chat_id = submission.get("assigned_doctor", {}).get("telegram_chat_id") or TELEGRAM_CHAT_ID
    if not (TELEGRAM_BOT_TOKEN and chat_id):
        return False, "Telegram-уведомление не настроено."

    patient = submission["patient"]
    reason = format_submission_reasons(submission)
    text = "\n".join(
        [
            "Новая анкета эндокринолога",
            f"Пациент: {format_answer(patient.get('full_name'))}",
            f"Телефон: {format_answer(patient.get('phone'))}",
            f"Причина: {reason}",
            f"ID: {submission['id']}",
            f"Открыть кабинет: {PUBLIC_URL}",
        ]
    )
    payload = urlencode({"chat_id": chat_id, "text": text})
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{payload}"
    with urlopen(url, timeout=15) as response:
        if response.status != 200:
            return False, f"Telegram вернул HTTP {response.status}."
    return True, "Telegram-уведомление отправлено."


def load_submissions() -> list[dict[str, Any]]:
    init_storage()
    submissions = []
    for path in SUBMISSIONS_DIR.glob("*.json"):
        try:
            submissions.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(submissions, key=lambda item: item.get("created_at", ""), reverse=True)


def update_submission_status(submission_id: str, status: str) -> None:
    path = SUBMISSIONS_DIR / f"{submission_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Анкета {submission_id} не найдена")
    submission = json.loads(path.read_text(encoding="utf-8"))
    submission["status"] = status
    if status in {"viewed", "in_progress", "closed"}:
        submission["viewed_at"] = submission.get("viewed_at") or now_iso()
    write_submission_record(submission)


def update_doctor_fields(
    submission_id: str,
    status: str,
    note: str,
    requested_documents: str,
    appointment_date: str,
) -> None:
    path = SUBMISSIONS_DIR / f"{submission_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Анкета {submission_id} не найдена")
    submission = json.loads(path.read_text(encoding="utf-8"))
    submission["status"] = status
    if status in {"viewed", "in_progress", "closed"}:
        submission["viewed_at"] = submission.get("viewed_at") or now_iso()
    submission["doctor"] = {
        "note": note.strip(),
        "requested_documents": requested_documents.strip(),
        "appointment_date": appointment_date.strip(),
        "updated_at": now_iso(),
    }
    write_submission_record(submission)


def get_submission_doctor_id(submission: dict[str, Any]) -> str:
    return str(submission.get("assigned_doctor", {}).get("id") or "")


def doctor_can_view_submission(submission: dict[str, Any]) -> bool:
    if st.session_state.get("doctor_role") == "admin":
        return True
    return get_submission_doctor_id(submission) == st.session_state.get("doctor_id")


def filter_submissions(
    submissions: list[dict[str, Any]],
    search_query: str,
    reason_filter: str,
    status_filter: str,
    doctor_filter: str = "Все",
) -> list[dict[str, Any]]:
    query = search_query.strip().lower()
    filtered = []
    for item in submissions:
        patient = item.get("patient", {})
        reason_labels = get_submission_reason_labels(item)
        reason_label = ", ".join(reason_labels)
        doctor_label = doctor_display_name(item.get("assigned_doctor"))
        haystack = " ".join(
            [
                str(patient.get("full_name", "")),
                str(patient.get("phone", "")),
                str(patient.get("city", "")),
                str(reason_label),
                str(doctor_label),
                str(item.get("id", "")),
            ]
        ).lower()
        if query and query not in haystack:
            continue
        if reason_filter != "Все" and reason_filter not in reason_labels:
            continue
        if status_filter != "Все" and item.get("status", "submitted") != status_filter:
            continue
        if doctor_filter != "Все" and doctor_label != doctor_filter:
            continue
        filtered.append(item)
    return filtered


def render_patient_form() -> None:
    st.title(APP_TITLE)
    st.caption("Предварительный сбор анамнеза перед консультацией эндокринолога")
    doctors = load_doctors()
    assigned_doctor = resolve_patient_doctor(doctors)
    st.info(f"Анкета будет отправлена врачу: {doctor_display_name(assigned_doctor)}")

    with st.expander("Что важно знать перед заполнением", expanded=True):
        st.write(
            "Анкета не ставит диагноз и не назначает лечение. "
            "Ответы нужны врачу для подготовки к приему. "
            "При острых симптомах обратитесь за срочной медицинской помощью."
        )

    st.subheader("Базовые данные")
    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("ФИО", key="patient_full_name")
        age = st.number_input("Возраст", min_value=0, max_value=120, step=1, key="patient_age")
        sex = st.selectbox("Пол", ["Женский", "Мужской"], key="patient_sex")
        phone = st.text_input("Телефон для связи", key="patient_phone")
    with col2:
        city = st.text_input("Город", key="patient_city")
        height_cm = st.number_input("Рост, см", min_value=0, max_value=250, step=1, key="patient_height")
        weight_kg = st.number_input("Вес, кг", min_value=0.0, max_value=400.0, step=0.5, key="patient_weight")
    reproductive_status = "Не применимо"
    if sex == "Женский":
        reproductive_status = st.selectbox(
            "Беременность / лактация",
            ["Нет", "Беременность", "Лактация", "Планирую беременность", "Менопауза", "Не знаю"],
            key="patient_reproductive_status",
        )

    st.subheader("Срочные симптомы")
    urgent_symptoms = st.multiselect(
        "Есть ли сейчас что-то из перечисленного?",
        URGENT_SYMPTOMS,
        key="urgent_symptoms",
    )
    selected_urgent_symptoms = [item for item in urgent_symptoms if item != NO_URGENT_SYMPTOMS]

    st.subheader("Причина обращения")
    selected_reasons = st.multiselect(
        "Что является причиной обращения? Можно выбрать несколько вариантов.",
        list(MAIN_REASONS.keys()),
        format_func=lambda reason: MAIN_REASONS[reason],
        key="main_reasons",
    )

    common = render_common_questions()
    branch = render_branches(selected_reasons, sex) if selected_reasons else {}

    st.subheader("Файлы и комментарий")
    uploaded_files = st.file_uploader(
        "Загрузите анализы, УЗИ, выписки, если есть",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="uploaded_files",
    )
    additional_comment = st.text_area("Хотите добавить что-то важное для врача?", key="additional_comment")

    preview_submission = {
        "id": "preview",
        "created_at": now_iso(),
        "status": "submitted",
        "assigned_doctor": public_doctor_info(assigned_doctor),
        "main_reasons": selected_reasons,
        "urgent_symptoms": selected_urgent_symptoms or ([NO_URGENT_SYMPTOMS] if NO_URGENT_SYMPTOMS in urgent_symptoms else []),
        "patient": {
            "full_name": full_name.strip(),
            "age": int(age),
            "sex": sex,
            "phone": phone.strip(),
            "city": city.strip(),
            "height_cm": int(height_cm) if height_cm else None,
            "weight_kg": float(weight_kg) if weight_kg else None,
            "reproductive_status": reproductive_status,
        },
        "common": common,
        "branch": branch,
        "additional_comment": additional_comment,
        "files": [
            {
                "original_name": uploaded_file.name,
                "stored_name": uploaded_file.name,
                "path": "",
                "type": uploaded_file.type,
                "size": uploaded_file.size,
            }
            for uploaded_file in (uploaded_files or [])
        ],
    }

    with st.expander("Предпросмотр резюме перед отправкой", expanded=False):
        st.text(build_summary(preview_submission))

    st.subheader("Согласие и отправка")
    consent = st.checkbox(
        "Я согласен/согласна на обработку и передачу врачу введенных персональных и медицинских данных.",
        key="consent",
    )
    submitted = st.button("Отправить анкету врачу", type="primary")

    if selected_urgent_symptoms:
        st.error(
            "Вы отметили потенциально срочные симптомы. Анкета не предназначена для экстренных ситуаций: "
            "обратитесь за срочной медицинской помощью или вызовите скорую."
        )

    if not submitted:
        return

    errors = []
    if not consent:
        errors.append("Нужно подтвердить согласие на обработку данных.")
    if not full_name.strip():
        errors.append("Укажите ФИО.")
    if not phone.strip():
        errors.append("Укажите телефон для связи.")
    if age <= 0:
        errors.append("Укажите возраст.")
    if not selected_reasons:
        errors.append("Выберите хотя бы одну причину обращения.")

    if errors:
        for error in errors:
            st.error(error)
        return

    submission = {**preview_submission, "id": str(uuid.uuid4()), "created_at": now_iso(), "files": []}
    submission_id = save_submission(submission, uploaded_files or [])
    st.success("Анкета отправлена врачу.")
    st.info(f"Номер анкеты: {submission_id}")
    try:
        email_sent, email_message = send_submission_email(submission)
        if email_sent:
            st.success(email_message)
        else:
            st.warning(email_message)
    except Exception as exc:
        st.warning(f"Анкета сохранена, но email-копию отправить не удалось: {exc}")
    try:
        telegram_sent, telegram_message = send_telegram_notification(submission)
        if telegram_sent:
            st.success(telegram_message)
    except Exception as exc:
        st.warning(f"Анкета сохранена, но Telegram-уведомление отправить не удалось: {exc}")
    with st.expander("Предварительное резюме", expanded=True):
        st.text(submission["summary"])


def render_doctor_dashboard() -> None:
    st.title("Кабинет врача")
    st.caption("Просмотр заполненных анкет и загруженных файлов")
    doctors = load_doctors()

    if ADMIN_PASSWORD == "admin":
        st.warning("Используется пароль по умолчанию. На сервере задайте ANAMNES_ADMIN_PASSWORD.")

    if not st.session_state.get("doctor_authenticated"):
        login = st.text_input("Логин врача или admin", value="admin")
        password = st.text_input("Пароль врача", type="password")
        if st.button("Войти"):
            doctor = get_doctor_by_id(doctors, login.strip().lower())
            if login.strip().lower() == "admin" and password == ADMIN_PASSWORD:
                st.session_state["doctor_authenticated"] = True
                st.session_state["doctor_role"] = "admin"
                st.session_state["doctor_id"] = ""
                st.session_state["doctor_name"] = "Администратор"
                st.rerun()
            elif doctor and password and password == doctor.get("password"):
                st.session_state["doctor_authenticated"] = True
                st.session_state["doctor_role"] = "doctor"
                st.session_state["doctor_id"] = doctor["id"]
                st.session_state["doctor_name"] = doctor["name"]
                st.rerun()
            else:
                st.error("Неверный пароль.")
        return

    if st.button("Выйти"):
        st.session_state["doctor_authenticated"] = False
        st.session_state["doctor_role"] = ""
        st.session_state["doctor_id"] = ""
        st.session_state["doctor_name"] = ""
        st.rerun()

    st.caption(
        f"Роль: {'администратор' if st.session_state.get('doctor_role') == 'admin' else 'врач'}; "
        f"пользователь: {st.session_state.get('doctor_name')}"
    )

    submissions = [item for item in load_submissions() if doctor_can_view_submission(item)]
    if not submissions:
        st.info("Пока нет отправленных анкет.")
        return

    viewed_count = sum(1 for item in submissions if item.get("status") == "viewed")
    new_count = sum(1 for item in submissions if item.get("status", "submitted") == "submitted")
    red_flag_count = sum(1 for item in submissions if get_red_flags(item))
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Всего анкет", len(submissions))
    metric_col2.metric("Новые", new_count)
    metric_col3.metric("Просмотренные", viewed_count)
    metric_col4.metric("С красными флагами", red_flag_count)

    st.subheader("Поиск и фильтры")
    filter_columns = st.columns(4 if st.session_state.get("doctor_role") == "admin" else 3)
    filter_col1, filter_col2, filter_col3 = filter_columns[:3]
    with filter_col1:
        search_query = st.text_input("Поиск по ФИО, телефону, городу или ID", key="doctor_search")
    with filter_col2:
        reason_options = ["Все"] + sorted(
            {reason for item in submissions for reason in get_submission_reason_labels(item)}
        )
        reason_filter = st.selectbox("Причина обращения", reason_options, key="doctor_reason_filter")
    with filter_col3:
        status_filter = st.selectbox(
            "Статус",
            ["Все", *SUBMISSION_STATUSES.keys()],
            format_func=lambda value: SUBMISSION_STATUSES.get(value, value),
            key="doctor_status_filter",
        )
    doctor_filter = "Все"
    if st.session_state.get("doctor_role") == "admin":
        with filter_columns[3]:
            doctor_options = ["Все"] + sorted({doctor_display_name(item.get("assigned_doctor")) for item in submissions})
            doctor_filter = st.selectbox("Врач", doctor_options, key="doctor_filter")

    filtered_submissions = filter_submissions(submissions, search_query, reason_filter, status_filter, doctor_filter)
    if not filtered_submissions:
        st.info("По выбранным фильтрам анкет нет.")
        return

    labels = {
        item["id"]: (
            f"{'!' if get_red_flags(item) else ('✓' if item.get('status') == 'viewed' else '•')} "
            f"{item['patient'].get('full_name', 'Без имени')} | "
            f"{doctor_display_name(item.get('assigned_doctor'))} | "
            f"{format_submission_reasons(item)} | "
            f"{SUBMISSION_STATUSES.get(item.get('status', 'submitted'), item.get('status'))} | "
            f"{item.get('created_at')}"
        )
        for item in filtered_submissions
    }
    selected_id = st.selectbox("Выберите анкету", list(labels), format_func=lambda item_id: labels[item_id])
    submission = next(item for item in filtered_submissions if item["id"] == selected_id)

    patient = submission["patient"]
    bmi = calculate_bmi(patient.get("height_cm"), patient.get("weight_kg"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Возраст", patient.get("age", "—"))
    col2.metric("Вес", patient.get("weight_kg", "—"))
    col3.metric("ИМТ", bmi if bmi is not None else "—")
    col4.metric("Статус", SUBMISSION_STATUSES.get(submission.get("status", "submitted"), submission.get("status")))

    red_flags = get_red_flags(submission)
    if red_flags:
        st.error("ВНИМАНИЕ: отмечены срочные симптомы: " + ", ".join(red_flags))

    if submission.get("status") != "viewed":
        if st.button("Отметить как просмотрено", type="primary"):
            update_submission_status(submission["id"], "viewed")
            st.success("Анкета отмечена как просмотренная.")
            st.rerun()

    st.subheader("Служебные поля врача")
    doctor = submission.get("doctor", {})
    with st.form(f"doctor_fields_{submission['id']}"):
        doctor_status = st.selectbox(
            "Статус анкеты",
            list(SUBMISSION_STATUSES.keys()),
            index=list(SUBMISSION_STATUSES.keys()).index(submission.get("status", "submitted"))
            if submission.get("status", "submitted") in SUBMISSION_STATUSES
            else 0,
            format_func=lambda value: SUBMISSION_STATUSES[value],
        )
        appointment_date = st.text_input("Дата приема", value=doctor.get("appointment_date", ""))
        requested_documents = st.text_area(
            "Что попросить пациента донести",
            value=doctor.get("requested_documents", ""),
        )
        doctor_note = st.text_area("Комментарий врача", value=doctor.get("note", ""))
        save_doctor_fields = st.form_submit_button("Сохранить служебные поля")
    if save_doctor_fields:
        update_doctor_fields(
            submission["id"],
            doctor_status,
            doctor_note,
            requested_documents,
            appointment_date,
        )
        st.success("Служебные поля сохранены.")
        st.rerun()

    st.subheader("Резюме для врача")
    st.text(submission.get("summary", "Резюме не сформировано"))
    st.download_button(
        "Скачать резюме TXT",
        data=submission.get("summary", ""),
        file_name=f"summary_{submission['id']}.txt",
        mime="text/plain",
    )
    st.download_button(
        "Скачать резюме PDF",
        data=build_summary_pdf(
            submission.get("summary", ""),
            f"Резюме анамнеза: {patient.get('full_name', 'Пациент')}",
        ),
        file_name=f"summary_{submission['id']}.pdf",
        mime="application/pdf",
    )

    st.subheader("Все ответы")
    st.json(
        {
            "patient": submission.get("patient"),
            "assigned_doctor": submission.get("assigned_doctor"),
            "urgent_symptoms": submission.get("urgent_symptoms"),
            "main_reasons": get_submission_reason_labels(submission),
            "common": submission.get("common"),
            "branch": submission.get("branch"),
            "additional_comment": submission.get("additional_comment"),
            "doctor": submission.get("doctor"),
        },
        expanded=False,
    )
    st.download_button(
        "Скачать JSON",
        data=json.dumps(submission, ensure_ascii=False, indent=2),
        file_name=f"submission_{submission['id']}.json",
        mime="application/json",
    )

    st.subheader("Файлы")
    files = submission.get("files", [])
    if not files:
        st.write("Файлы не загружены.")
    for file_info in files:
        path = Path(file_info["path"])
        if not path.exists():
            st.warning(f"Файл не найден: {file_info['original_name']}")
            continue
        st.write(f"{file_info['original_name']} ({file_info.get('type') or 'unknown'})")
        st.download_button(
            f"Скачать {file_info['original_name']}",
            data=path.read_bytes(),
            file_name=file_info["original_name"],
            mime=file_info.get("type") or "application/octet-stream",
            key=f"download_{submission['id']}_{file_info['stored_name']}",
        )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")
    init_storage()

    with st.sidebar:
        st.header(APP_TITLE)
        page = st.radio("Раздел", ["Анкета пациента", "Кабинет врача"])
        st.divider()
        st.caption("MVP для тестирования. Не используйте реальные данные без HTTPS и настроенного доступа.")

    if page == "Анкета пациента":
        render_patient_form()
    else:
        render_doctor_dashboard()


if __name__ == "__main__":
    main()
