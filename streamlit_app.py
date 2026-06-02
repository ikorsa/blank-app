import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


def _load_local_env() -> None:
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

import anamnes_storage as store
from anamnes_storage import (
    delete_draft,
    load_doctors,
    load_draft,
    load_submissions,
    save_draft_record,
    set_doctor_active,
    update_doctor_fields,
    update_submission_status,
    upsert_doctor,
    use_postgres,
    write_submission_record,
)

import streamlit as st
from doctor_notifications import (
    notification_status_lines,
    notify_doctor_on_submission,
    send_test_notifications,
)
from patient_wizard import (
    init_wizard_state,
    make_qr_image,
    patient_web_url,
    render_intro,
    render_nav,
    render_progress_bar,
    render_qr_page,
    render_submission_success,
)
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
DRAFTS_DIR = DATA_DIR / "drafts"
DRAFT_UPLOADS_DIR = DATA_DIR / "draft_uploads"
DRAFT_RETENTION_DAYS = int(os.getenv("ANAMNES_DRAFT_RETENTION_DAYS", "30"))
AUTOSAVE_INTERVAL_SECONDS = int(os.getenv("ANAMNES_AUTOSAVE_INTERVAL_SECONDS", "150"))
DOCTORS_FILE = Path(os.getenv("ANAMNES_DOCTORS_FILE", str(DATA_DIR / "doctors.json")))
ADMIN_PASSWORD = os.getenv("ANAMNES_ADMIN_PASSWORD", "admin")
PDF_FONT_NAME = "DejaVuSans"
PUBLIC_URL = os.getenv("ANAMNES_PUBLIC_URL", "https://anamnes.ikorsakov.tech")
TELEGRAM_BOT_USERNAME = os.getenv("ANAMNES_TELEGRAM_BOT_USERNAME", "ikorsakov_anamnes_bot").lstrip("@")

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
    store.init_storage()
    store.purge_expired_drafts()


BRANCH_SESSION_KEYS: dict[str, dict[str, str]] = {
    "thyroid": {
        "diagnosis": "thyroid_diagnosis",
        "medications": "thyroid_medications",
        "dose": "thyroid_dose",
        "last_lab_date": "thyroid_last_lab_date",
        "last_tsh_date": "thyroid_last_tsh_date",
        "last_tsh_value": "thyroid_last_tsh_value",
        "free_t4_value": "thyroid_free_t4",
        "free_t3_value": "thyroid_free_t3",
        "antibodies": "thyroid_antibodies",
        "ultrasound": "thyroid_ultrasound",
        "ultrasound_findings": "thyroid_ultrasound_findings",
        "symptoms": "thyroid_symptoms",
    },
    "diabetes": {
        "diagnosis": "diabetes_diagnosis",
        "first_detected": "diabetes_first_detected",
        "medications": "diabetes_medications",
        "medications_details": "diabetes_medications_details",
        "insulin": "diabetes_insulin",
        "fasting_glucose": "diabetes_fasting_glucose",
        "post_meal_glucose": "diabetes_post_meal_glucose",
        "hba1c": "diabetes_hba1c",
        "hypoglycemia": "diabetes_hypoglycemia",
        "complications": "diabetes_complications",
        "insulin_types": "diabetes_insulin_types",
        "insulin_regimen": "diabetes_insulin_regimen",
        "insulin_daily_units": "diabetes_insulin_daily_units",
    },
    "weight": {
        "waist_cm": "weight_waist_cm",
        "weight_gain_started": "weight_gain_started",
        "weight_gain_amount": "weight_gain_amount",
        "max_weight": "weight_max_weight",
        "appetite": "weight_appetite",
        "previous_attempts": "weight_previous_attempts",
        "weight_loss_result": "weight_loss_result",
        "night_eating": "weight_night_eating",
        "snoring": "weight_snoring",
        "sleep_duration": "weight_sleep_duration",
        "physical_activity": "weight_physical_activity",
        "hypertension": "weight_hypertension",
        "weight_gain_medications": "weight_gain_medications",
        "metabolic_tests": "weight_metabolic_tests",
    },
    "hormones": {
        "libido": "hormones_libido",
        "fertility": "hormones_fertility",
        "hormonal_meds": "hormones_meds_male",
        "cycle_regular": "hormones_cycle_regular",
        "cycle_length": "hormones_cycle_length",
        "long_delays": "hormones_long_delays",
        "acne": "hormones_acne",
        "hirsutism": "hormones_hirsutism",
        "hair_loss": "hormones_hair_loss",
        "pregnancy_history": "hormones_pregnancy_history",
        "pregnancy_plans": "hormones_pregnancy_plans",
    },
    "fatigue": {
        "main_issue": "fatigue_main_issue",
        "duration": "fatigue_duration",
        "weight_change": "fatigue_weight_change",
        "sleep": "fatigue_sleep",
        "recent_tests": "fatigue_recent_tests",
    },
    "bone": {
        "diagnosis": "bone_diagnosis",
        "low_trauma_fractures": "bone_fractures",
        "densitometry": "bone_densitometry",
        "supplements": "bone_supplements",
        "kidney_stones": "bone_kidney_stones",
    },
    "other": {
        "details": "other_details",
        "expectations": "other_expectations",
    },
}

COMMON_SESSION_KEYS = {
    "complaints": "common_complaints",
    "complaints_started": "common_complaints_started",
    "chronic_conditions": "common_chronic",
    "chronic_conditions_other": "common_chronic_other",
    "surgeries": "common_surgeries",
    "medications": "common_medications_select",
    "medications_details": "common_medications_details",
    "allergy_status": "common_allergy_status",
    "allergies_details": "common_allergies_details",
    "family_history": "common_family_history",
    "blood_pressure": "common_bp",
    "smoking": "common_smoking",
}


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


def collect_common_from_session() -> dict[str, Any]:
    chronic = st.session_state.get("common_chronic", [])
    allergy_status = st.session_state.get("common_allergy_status", "Нет")
    return {
        "complaints": st.session_state.get("common_complaints", ""),
        "complaints_started": st.session_state.get("common_complaints_started", ""),
        "chronic_conditions": chronic,
        "chronic_conditions_other": st.session_state.get("common_chronic_other", "")
        if "Другое" in chronic
        else "",
        "surgeries": st.session_state.get("common_surgeries", ""),
        "medications": st.session_state.get("common_medications_select", []),
        "medications_details": st.session_state.get("common_medications_details", ""),
        "allergy_status": allergy_status,
        "allergies_details": st.session_state.get("common_allergies_details", "")
        if allergy_status == "Да"
        else "",
        "family_history": st.session_state.get("common_family_history", []),
        "blood_pressure": st.session_state.get("common_bp", ""),
        "smoking": st.session_state.get("common_smoking", "Нет"),
    }


def collect_branch_from_session(reasons: list[str], sex: str) -> dict[str, Any]:
    branches: dict[str, Any] = {}
    for reason in reasons:
        mapping = BRANCH_SESSION_KEYS.get(reason, {})
        answers: dict[str, Any] = {}
        for field, key in mapping.items():
            if field == "hormonal_meds" and reason == "hormones":
                key = "hormones_meds_male" if sex == "Мужской" else "hormones_meds"
            if key in st.session_state:
                answers[field] = st.session_state[key]
        if answers:
            branches[reason] = answers
    return branches


def get_selected_reasons() -> list[str]:
    current = st.session_state.get("main_reasons")
    if isinstance(current, list) and current:
        st.session_state["wizard_main_reasons_snapshot"] = list(current)
        return current
    snapshot = st.session_state.get("wizard_main_reasons_snapshot")
    if isinstance(snapshot, list) and snapshot:
        return snapshot
    return []


def get_patient_field_value(field: str, default: Any = "") -> Any:
    snapshot = st.session_state.get("wizard_patient_snapshot") or {}
    if field in st.session_state:
        value = st.session_state.get(field)
        snapshot[field] = value
        st.session_state["wizard_patient_snapshot"] = snapshot
        return value
    if field in snapshot:
        return snapshot[field]
    return default


def sync_patient_snapshot() -> None:
    fields = (
        "patient_full_name",
        "patient_age",
        "patient_sex",
        "patient_phone",
        "patient_city",
        "patient_height",
        "patient_weight",
        "patient_reproductive_status",
        "urgent_symptoms",
    )
    snapshot = st.session_state.get("wizard_patient_snapshot") or {}
    changed = False
    for field in fields:
        if field in st.session_state:
            snapshot[field] = st.session_state[field]
            changed = True
    if changed:
        st.session_state["wizard_patient_snapshot"] = snapshot


def resolve_selected_reasons_for_save() -> list[str]:
    reasons = get_selected_reasons()
    if reasons:
        return reasons
    active_draft_id = st.session_state.get("active_draft_id")
    if active_draft_id:
        existing = load_draft(str(active_draft_id)) or {}
        existing_reasons = existing.get("main_reasons")
        if isinstance(existing_reasons, list) and existing_reasons:
            st.session_state["wizard_main_reasons_snapshot"] = list(existing_reasons)
            return existing_reasons
    return []


def hydrate_patient_state_from_snapshot() -> None:
    snapshot = st.session_state.get("wizard_patient_snapshot") or {}
    if not snapshot:
        return
    for field, value in snapshot.items():
        if field not in st.session_state or _is_blank_value(st.session_state.get(field)):
            st.session_state[field] = value


def build_patient_payload_from_session(assigned_doctor: dict[str, str]) -> dict[str, Any]:
    """
    Собирает payload анкеты из текущего session_state.
    Используется для кнопки сохранения черновика с любого шага.
    """
    full_name = str(get_patient_field_value("patient_full_name", ""))
    age = int(get_patient_field_value("patient_age", 0) or 0)
    sex = str(get_patient_field_value("patient_sex", "Женский"))
    phone = str(get_patient_field_value("patient_phone", ""))
    city = str(get_patient_field_value("patient_city", ""))
    height_cm = int(get_patient_field_value("patient_height", 0) or 0)
    weight_kg = float(get_patient_field_value("patient_weight", 0.0) or 0.0)

    reproductive_status = (
        get_patient_field_value("patient_reproductive_status", "Нет") if sex == "Женский" else "Не применимо"
    )

    urgent_symptoms = get_patient_field_value("urgent_symptoms", [NO_URGENT_SYMPTOMS]) or [NO_URGENT_SYMPTOMS]
    selected_urgent = [x for x in urgent_symptoms if x != NO_URGENT_SYMPTOMS]

    selected_reasons = resolve_selected_reasons_for_save()
    common = collect_common_from_session()
    branch = collect_branch_from_session(selected_reasons, sex)

    additional_comment = str(st.session_state.get("additional_comment", ""))

    return build_patient_form_payload(
        assigned_doctor=assigned_doctor,
        full_name=full_name,
        age=age,
        sex=sex,
        phone=phone,
        city=city,
        height_cm=height_cm,
        weight_kg=weight_kg,
        reproductive_status=reproductive_status,
        selected_reasons=selected_reasons,
        selected_urgent_symptoms=selected_urgent,
        urgent_symptoms=urgent_symptoms,
        common=common,
        branch=branch,
        additional_comment=additional_comment,
    )


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


def draft_resume_url(doctor_id: str, draft_id: str) -> str:
    return f"{PUBLIC_URL.rstrip('/')}/?{urlencode({'doctor': doctor_id, 'draft': draft_id})}"


def apply_draft_to_session(draft: dict[str, Any]) -> None:
    patient = draft.get("patient", {})
    st.session_state["patient_full_name"] = patient.get("full_name", "")
    st.session_state["patient_age"] = int(patient.get("age") or 0)
    st.session_state["patient_sex"] = patient.get("sex", "Женский")
    st.session_state["patient_phone"] = patient.get("phone", "")
    st.session_state["patient_city"] = patient.get("city", "")
    st.session_state["patient_height"] = int(patient.get("height_cm") or 0)
    st.session_state["patient_weight"] = float(patient.get("weight_kg") or 0.0)
    if patient.get("sex") == "Женский":
        st.session_state["patient_reproductive_status"] = patient.get("reproductive_status", "Нет")

    urgent = draft.get("urgent_symptoms") or []
    st.session_state["urgent_symptoms"] = urgent if urgent else [NO_URGENT_SYMPTOMS]
    st.session_state["main_reasons"] = draft.get("main_reasons") or []
    st.session_state["wizard_main_reasons_snapshot"] = list(draft.get("main_reasons") or [])
    st.session_state["additional_comment"] = draft.get("additional_comment", "")
    st.session_state["wizard_patient_snapshot"] = {
        "patient_full_name": st.session_state.get("patient_full_name", ""),
        "patient_age": st.session_state.get("patient_age", 0),
        "patient_sex": st.session_state.get("patient_sex", "Женский"),
        "patient_phone": st.session_state.get("patient_phone", ""),
        "patient_city": st.session_state.get("patient_city", ""),
        "patient_height": st.session_state.get("patient_height", 0),
        "patient_weight": st.session_state.get("patient_weight", 0.0),
        "patient_reproductive_status": st.session_state.get("patient_reproductive_status", "Нет"),
        "urgent_symptoms": st.session_state.get("urgent_symptoms", [NO_URGENT_SYMPTOMS]),
    }

    common = draft.get("common") or {}
    for field, key in COMMON_SESSION_KEYS.items():
        if field in common:
            st.session_state[key] = common[field]

    branch = draft.get("branch") or {}
    sex = patient.get("sex", "Женский")
    for reason, answers in branch.items():
        if not isinstance(answers, dict):
            continue
        mapping = BRANCH_SESSION_KEYS.get(reason, {})
        for field, value in answers.items():
            if field == "hormonal_meds" and reason == "hormones":
                key = "hormones_meds_male" if sex == "Мужской" else "hormones_meds"
            else:
                key = mapping.get(field)
            if key:
                st.session_state[key] = value


def init_draft_from_query() -> str | None:
    draft_id = get_query_param("draft").strip()
    if not draft_id:
        return st.session_state.get("active_draft_id")

    draft_id = safe_filename(draft_id)
    draft = load_draft(draft_id)
    if not draft:
        st.warning("Черновик не найден или срок хранения истёк.")
        return None

    applied_version_key = f"draft_applied_updated_at_{draft_id}"
    draft_updated_at = str(draft.get("updated_at", ""))
    already_applied_same_version = st.session_state.get(applied_version_key) == draft_updated_at and bool(draft_updated_at)
    if already_applied_same_version:
        st.session_state["active_draft_id"] = draft_id
        return draft_id

    apply_draft_to_session(draft)
    st.session_state[f"draft_applied_{draft_id}"] = True
    st.session_state[applied_version_key] = draft_updated_at
    st.session_state["active_draft_id"] = draft_id
    st.session_state["draft_last_autosave_ts"] = time.time()
    st.session_state.pop("draft_files_to_remove", None)
    return draft_id


def save_draft_files(
    draft_id: str,
    uploaded_files: list[Any],
    existing_files: list[dict[str, Any]],
    remove_stored: set[str],
) -> list[dict[str, Any]]:
    upload_dir = DRAFT_UPLOADS_DIR / draft_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []

    for file_info in existing_files:
        stored_name = file_info.get("stored_name", "")
        if stored_name in remove_stored:
            path = Path(file_info.get("path", ""))
            if path.exists():
                path.unlink()
            continue
        if Path(file_info.get("path", "")).exists():
            saved_files.append(file_info)

    for uploaded_file in uploaded_files or []:
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
    return saved_files


def _is_blank_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    if isinstance(value, (int, float)):
        return value == 0
    return False


def _merge_prefer_filled(new_value: Any, old_value: Any) -> Any:
    """
    Не затираем заполненные поля старого черновика пустыми значениями.
    """
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        merged = dict(old_value)
        for key, value in new_value.items():
            merged[key] = _merge_prefer_filled(value, old_value.get(key))
        return merged
    if isinstance(new_value, list):
        return new_value if new_value else (old_value if isinstance(old_value, list) else new_value)
    if _is_blank_value(new_value):
        return old_value
    return new_value


def save_draft(
    draft_payload: dict[str, Any],
    uploaded_files: list[Any],
    draft_id: str | None = None,
) -> str:
    init_storage()
    draft_id = safe_filename(draft_id or str(uuid.uuid4()))
    existing = load_draft(draft_id) or {}
    payload = _merge_prefer_filled(draft_payload, existing) if existing else draft_payload
    remove_stored = set(st.session_state.get("draft_files_to_remove") or [])
    existing_files = existing.get("files", [])
    saved_files = save_draft_files(draft_id, uploaded_files, existing_files, remove_stored)

    now = now_iso()
    draft = {
        **payload,
        "id": draft_id,
        "status": "draft",
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "files": saved_files,
    }
    save_draft_record(draft)
    st.session_state["active_draft_id"] = draft_id
    st.session_state[f"draft_applied_{draft_id}"] = True
    st.session_state["draft_last_autosave_ts"] = time.time()
    st.session_state["draft_files_to_remove"] = []
    return draft_id


def render_draft_saved_files(draft_id: str, files: list[dict[str, Any]]) -> None:
    if not files:
        return
    st.caption("Файлы, уже сохранённые в черновике:")
    remove_list = list(st.session_state.get("draft_files_to_remove") or [])
    for file_info in files:
        path = Path(file_info.get("path", ""))
        col1, col2 = st.columns([4, 1])
        with col1:
            if path.exists():
                st.download_button(
                    f"Скачать {file_info['original_name']}",
                    data=path.read_bytes(),
                    file_name=file_info["original_name"],
                    mime=file_info.get("type") or "application/octet-stream",
                    key=f"draft_dl_{draft_id}_{file_info['stored_name']}",
                )
            else:
                st.write(f"{file_info['original_name']} (файл не найден на сервере)")
        with col2:
            if st.button("Удалить", key=f"draft_rm_{draft_id}_{file_info['stored_name']}"):
                remove_list.append(file_info["stored_name"])
                st.session_state["draft_files_to_remove"] = remove_list
                st.rerun()
    st.session_state["draft_files_to_remove"] = remove_list


def maybe_autosave_draft(
    draft_payload: dict[str, Any],
    uploaded_files: list[Any],
    draft_id: str | None,
) -> None:
    if not draft_id:
        return
    last_save = st.session_state.get("draft_last_autosave_ts", 0.0)
    if time.time() - last_save < AUTOSAVE_INTERVAL_SECONDS:
        return
    save_draft(draft_payload, uploaded_files, draft_id=draft_id)
    st.session_state["draft_autosave_notice"] = (
        f"Черновик автоматически сохранён ({datetime.now().strftime('%H:%M')})."
    )


def save_submission(
    submission: dict[str, Any],
    uploaded_files: list[Any],
    copy_files: list[dict[str, Any]] | None = None,
) -> str:
    init_storage()
    submission_id = submission["id"]
    upload_dir = UPLOADS_DIR / submission_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for file_info in copy_files or []:
        src = Path(file_info.get("path", ""))
        if not src.exists():
            continue
        filename = safe_filename(file_info.get("original_name") or src.name)
        path = upload_dir / filename
        counter = 1
        while path.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        data = src.read_bytes()
        path.write_bytes(data)
        saved_files.append(
            {
                "original_name": file_info.get("original_name") or filename,
                "stored_name": path.name,
                "path": str(path),
                "type": file_info.get("type"),
                "size": len(data),
            }
        )

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
    write_submission_record(submission)
    return submission_id


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


def build_patient_form_payload(
    assigned_doctor: dict[str, str],
    full_name: str,
    age: int,
    sex: str,
    phone: str,
    city: str,
    height_cm: int,
    weight_kg: float,
    reproductive_status: str,
    selected_reasons: list[str],
    selected_urgent_symptoms: list[str],
    urgent_symptoms: list[str],
    common: dict[str, Any],
    branch: dict[str, Any],
    additional_comment: str,
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "created_at": now_iso(),
        "assigned_doctor": public_doctor_info(assigned_doctor),
        "main_reasons": selected_reasons,
        "urgent_symptoms": selected_urgent_symptoms
        or ([NO_URGENT_SYMPTOMS] if NO_URGENT_SYMPTOMS in urgent_symptoms else []),
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
        "files": files or [],
    }


def reset_patient_wizard() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(("patient_", "common_", "thyroid_", "diabetes_", "weight_", "hormones_", "fatigue_", "bone_", "other_", "urgent_", "main_", "wizard_", "consent", "uploaded_", "draft_")):
            st.session_state.pop(key, None)
    st.session_state.patient_wizard_step = 0
    st.session_state.patient_submission_done = None


def render_patient_form() -> None:
    st.title(APP_TITLE)
    st.caption("Предварительный сбор анамнеза перед консультацией эндокринолога")
    doctors = load_doctors()
    active_draft_id = init_draft_from_query()
    assigned_doctor = resolve_patient_doctor(doctors)
    init_wizard_state(skip_intro=bool(active_draft_id))
    sync_patient_snapshot()
    hydrate_patient_state_from_snapshot()

    sidebar_save_clicked = False
    with st.sidebar:
        st.subheader("Черновик")
        current_draft_id = st.session_state.get("active_draft_id") or active_draft_id
        if current_draft_id:
            st.caption(f"Активный: {current_draft_id}")
            st.markdown("**Ссылка для продолжения черновика:**")
            st.text_input(
                "Скопируйте и сохраните ссылку",
                value=draft_resume_url(assigned_doctor["id"], current_draft_id),
                disabled=True,
                key="sidebar_draft_link",
            )
        uploaded_files_count = len(st.session_state.get("uploaded_files") or [])
        st.caption(f"Файлы в черновик: {uploaded_files_count}")
        sidebar_save_clicked = st.button(
            "Сохранить черновик (в любое время)",
            type="secondary",
            use_container_width=True,
            key="sidebar_save_draft_button",
        )

    if done := st.session_state.get("patient_submission_done"):
        for message in st.session_state.pop("submission_notify_ok", []):
            st.success(message)
        for message in st.session_state.pop("submission_notify_warn", []):
            st.caption(message)
        render_submission_success(
            done["id"],
            doctor_display_name(assigned_doctor),
            on_new=reset_patient_wizard,
        )
        return

    st.info(f"Анкета будет отправлена врачу: {doctor_display_name(assigned_doctor)}")

    if autosave_notice := st.session_state.pop("draft_autosave_notice", None):
        st.success(autosave_notice)
    if active_draft_id:
        draft_meta = load_draft(active_draft_id) or {}
        updated = draft_meta.get("updated_at", "")
        st.success(f"Загружен черновик (сохранён {updated}). Продолжите с того шага, где остановились.")
        resume = draft_resume_url(assigned_doctor["id"], active_draft_id)
        with st.expander("Ссылка для продолжения на другом устройстве"):
            st.code(resume, language=None)
            st.caption("Сохраните в «Избранное» или перешлите себе в Telegram. Без ссылки продолжить нельзя.")

    step = int(st.session_state.patient_wizard_step)

    if step == 0:

        def _start_wizard() -> None:
            st.session_state.patient_wizard_step = 1
            st.rerun()

        render_intro(doctor_display_name(assigned_doctor), on_start=_start_wizard)
        return

    render_progress_bar(step)

    if step == 1:
        st.subheader("Шаг 1. О вас")
        st.caption("Поля, отмеченные *, обязательны.")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("ФИО *", key="patient_full_name")
            st.number_input("Возраст *", min_value=0, max_value=120, step=1, key="patient_age")
            sex = st.selectbox("Пол *", ["Женский", "Мужской"], key="patient_sex")
            st.text_input("Телефон для связи *", key="patient_phone", placeholder="+7 ...")
        with col2:
            st.text_input("Город *", key="patient_city")
            st.number_input("Рост, см *", min_value=0, max_value=250, step=1, key="patient_height")
            st.number_input("Вес, кг *", min_value=0.0, max_value=400.0, step=0.5, key="patient_weight")
        if st.session_state.get("patient_sex") == "Женский":
            st.selectbox(
                "Беременность / лактация",
                ["Нет", "Беременность", "Лактация", "Планирую беременность", "Менопауза", "Не знаю"],
                key="patient_reproductive_status",
            )
        st.subheader("Срочные симптомы")
        st.multiselect("Есть ли сейчас что-то из перечисленного?", URGENT_SYMPTOMS, key="urgent_symptoms")
        st.caption("При острых симптомах — скорая помощь, не эта анкета.")
        back, nxt = render_nav(back=False)
        if nxt:
            missing_fields: list[str] = []
            if not str(st.session_state.get("patient_full_name", "")).strip():
                missing_fields.append("ФИО")
            if int(st.session_state.get("patient_age") or 0) <= 0:
                missing_fields.append("Возраст")
            if not str(st.session_state.get("patient_phone", "")).strip():
                missing_fields.append("Телефон для связи")
            if not str(st.session_state.get("patient_city", "")).strip():
                missing_fields.append("Город")
            if int(st.session_state.get("patient_height") or 0) <= 0:
                missing_fields.append("Рост")
            if float(st.session_state.get("patient_weight") or 0.0) <= 0:
                missing_fields.append("Вес")

            if missing_fields:
                formatted = "\n".join([f"- {field}" for field in missing_fields])
                st.error(f"Заполните обязательные поля:\n{formatted}")
            else:
                sync_patient_snapshot()
                st.session_state.patient_wizard_step = 2
                st.rerun()

    elif step == 2:
        st.subheader("Шаг 2. Причина обращения")
        snapshot_reasons = list(st.session_state.get("wizard_main_reasons_snapshot") or [])
        current_reasons = st.session_state.get("main_reasons")
        if not isinstance(current_reasons, list) or (not current_reasons and snapshot_reasons):
            st.session_state["main_reasons"] = snapshot_reasons
        prev_reasons = list(st.session_state.get("wizard_main_reasons_snapshot") or [])
        st.multiselect(
            "Что является причиной обращения? Можно выбрать несколько.",
            list(MAIN_REASONS.keys()),
            format_func=lambda reason: MAIN_REASONS[reason],
            key="main_reasons",
        )
        selected = get_selected_reasons()
        if prev_reasons and set(prev_reasons) != set(selected):
            st.warning("Вы изменили причину обращения — ответы в профильных блоках на следующем шаге нужно проверить заново.")
        back, nxt = render_nav()
        if back:
            st.session_state.patient_wizard_step = 1
            st.rerun()
        if nxt:
            if not selected:
                st.error("Выберите хотя бы одну причину обращения.")
            else:
                st.session_state.wizard_main_reasons_snapshot = list(selected)
                st.session_state.patient_wizard_step = 3
                st.rerun()

    elif step == 3:
        st.subheader("Шаг 3. Анамнез")
        sex = st.session_state.get("patient_sex", "Женский")
        selected_reasons = get_selected_reasons()
        render_common_questions()
        if selected_reasons:
            render_branches(selected_reasons, sex)
        else:
            st.info("Вернитесь на шаг 2 и выберите причину обращения.")
        back, nxt = render_nav()
        if back:
            st.session_state.patient_wizard_step = 2
            st.rerun()
        if nxt:
            if not selected_reasons:
                st.error("Выберите причину обращения на шаге 2.")
            else:
                st.session_state.patient_wizard_step = 4
                st.rerun()

    elif step == 4:
        st.subheader("Шаг 4. Файлы и комментарий")
        if active_draft_id:
            draft_record = load_draft(active_draft_id) or {}
            render_draft_saved_files(active_draft_id, draft_record.get("files", []))
        st.file_uploader(
            "Загрузите анализы, УЗИ, выписки (PDF, JPG, PNG). Можно сфотографировать выписку.",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="uploaded_files",
            help="Файлы сохраняются в черновике. До 25 МБ на файл.",
        )
        st.text_area("Дополнительный комментарий для врача", key="additional_comment")
        back, nxt = render_nav()
        if back:
            st.session_state.patient_wizard_step = 3
            st.rerun()
        if nxt:
            st.session_state.patient_wizard_step = 5
            st.rerun()

    elif step == 5:
        st.subheader("Шаг 5. Проверка и отправка")
        full_name = str(st.session_state.get("patient_full_name", ""))
        age = int(st.session_state.get("patient_age") or 0)
        sex = str(st.session_state.get("patient_sex", "Женский"))
        phone = str(st.session_state.get("patient_phone", ""))
        city = str(st.session_state.get("patient_city", ""))
        height_cm = int(st.session_state.get("patient_height") or 0)
        weight_kg = float(st.session_state.get("patient_weight") or 0.0)
        reproductive_status = (
            st.session_state.get("patient_reproductive_status", "Нет")
            if sex == "Женский"
            else "Не применимо"
        )
        urgent_symptoms = st.session_state.get("urgent_symptoms") or [NO_URGENT_SYMPTOMS]
        selected_urgent = [x for x in urgent_symptoms if x != NO_URGENT_SYMPTOMS]
        selected_reasons = get_selected_reasons()
        common = collect_common_from_session()
        branch = collect_branch_from_session(selected_reasons, sex)
        additional_comment = str(st.session_state.get("additional_comment", ""))
        uploaded_files = st.session_state.get("uploaded_files") or []

        form_payload = build_patient_form_payload(
            assigned_doctor,
            full_name,
            age,
            sex,
            phone,
            city,
            height_cm,
            weight_kg,
            reproductive_status,
            selected_reasons,
            selected_urgent,
            urgent_symptoms,
            common,
            branch,
            additional_comment,
        )
        preview = {**form_payload, "id": "preview", "status": "submitted"}

        if selected_urgent:
            st.error("Отмечены срочные симптомы — обратитесь за неотложной помощью, не только через анкету.")

        with st.expander("Предпросмотр для врача", expanded=False):
            st.text(build_summary(preview))

        st.subheader("Черновик")
        st.caption(
            f"Хранится до {DRAFT_RETENTION_DAYS} дн. Автосохранение каждые {AUTOSAVE_INTERVAL_SECONDS // 60} мин. "
            "при открытой ссылке с ?draft=..."
        )
        if st.button("Сохранить черновик и получить ссылку", type="secondary", use_container_width=True):
            draft_id = save_draft(form_payload, uploaded_files, draft_id=active_draft_id)
            st.query_params.from_dict({"doctor": assigned_doctor["id"], "draft": draft_id})
            link = draft_resume_url(assigned_doctor["id"], draft_id)
            st.success("Черновик сохранён.")
            st.markdown(
                "**Сохраните ссылку** — перешлите себе в Telegram или «Избранное». "
                "Без неё продолжить на другом устройстве нельзя."
            )
            st.code(link, language=None)

        consent = st.checkbox(
            "Я согласен/согласна на обработку и передачу врачу персональных и медицинских данных.",
            key="consent",
        )
        back, submit = render_nav(next_label="Отправить врачу →")
        if back:
            st.session_state.patient_wizard_step = 4
            st.rerun()

        maybe_autosave_draft(form_payload, uploaded_files, active_draft_id)

        if submit:
            errors = []
            if not consent:
                errors.append("Подтвердите согласие на обработку данных.")
            if not full_name.strip():
                errors.append("Укажите ФИО.")
            if not phone.strip():
                errors.append("Укажите телефон.")
            if age <= 0:
                errors.append("Укажите возраст.")
            if not selected_reasons:
                errors.append("Выберите причину обращения на шаге 2.")
            for error in errors:
                st.error(error)
            if not errors:
                draft_id = st.session_state.get("active_draft_id")
                draft_copy: list[dict[str, Any]] = []
                if draft_id:
                    draft_record = load_draft(draft_id) or {}
                    remove_stored = set(st.session_state.get("draft_files_to_remove") or [])
                    draft_copy = [
                        f for f in draft_record.get("files", []) if f.get("stored_name") not in remove_stored
                    ]
                submission = {
                    **preview,
                    "id": str(uuid.uuid4()),
                    "created_at": now_iso(),
                    "status": "submitted",
                    "files": [],
                }
                submission_id = save_submission(submission, uploaded_files, copy_files=draft_copy)
                if draft_id:
                    delete_draft(draft_id)
                    st.session_state.pop("active_draft_id", None)
                    st.session_state.pop(f"draft_applied_{draft_id}", None)
                for ok, message in notify_doctor_on_submission(submission):
                    if ok:
                        st.session_state.setdefault("submission_notify_ok", []).append(message)
                    else:
                        st.session_state.setdefault("submission_notify_warn", []).append(message)
                st.session_state.patient_submission_done = {
                    "id": submission_id,
                    "summary": submission.get("summary", ""),
                }
                st.rerun()

    if sidebar_save_clicked:
        if not assigned_doctor.get("id"):
            st.error("Врач не выбран — откройте страницу с ссылкой врача.")
        else:
            payload = build_patient_payload_from_session(assigned_doctor)
            uploaded_files = st.session_state.get("uploaded_files") or []
            current_draft_id = st.session_state.get("active_draft_id")
            draft_id = save_draft(payload, uploaded_files, draft_id=current_draft_id)
            st.query_params.from_dict({"doctor": assigned_doctor["id"], "draft": draft_id})
            st.rerun()


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


def render_admin_panel() -> None:
    st.title("Управление врачами")
    backend = "PostgreSQL" if use_postgres() else f"JSON ({DOCTORS_FILE})"
    st.caption(f"Хранилище: {backend}. Анкеты: {len(load_submissions())} шт.")

    if ADMIN_PASSWORD == "admin":
        st.warning("Используется пароль администратора по умолчанию. Задайте ANAMNES_ADMIN_PASSWORD.")

    if not st.session_state.get("admin_panel_authenticated"):
        login = st.text_input("Логин администратора", value="admin")
        password = st.text_input("Пароль администратора", type="password")
        if st.button("Войти в управление"):
            if login.strip().lower() == "admin" and password == ADMIN_PASSWORD:
                st.session_state["admin_panel_authenticated"] = True
                st.rerun()
            else:
                st.error("Неверный логин или пароль.")
        return

    if st.button("Выйти из управления"):
        st.session_state["admin_panel_authenticated"] = False
        st.rerun()

    with st.expander("Добавить врача", expanded=False):
        with st.form("admin_add_doctor"):
            new_id = st.text_input("Код врача (латиница)", placeholder="ivanova", help="Используется в ссылке ?doctor=...")
            new_name = st.text_input("ФИО")
            new_specialty = st.text_input("Специальность", value="Эндокринолог")
            new_email = st.text_input("Email для уведомлений")
            new_telegram = st.text_input("Telegram chat_id врача")
            new_password = st.text_input("Пароль для кабинета врача", type="password")
            if st.form_submit_button("Создать врача"):
                try:
                    upsert_doctor(
                        {
                            "id": new_id.strip().lower(),
                            "name": new_name.strip(),
                            "specialty": new_specialty.strip() or "Эндокринолог",
                            "email": new_email.strip(),
                            "telegram_chat_id": new_telegram.strip(),
                            "password": new_password,
                            "is_active": True,
                        }
                    )
                    st.success(f"Врач {new_id.strip().lower()} создан.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    doctors = load_doctors(include_inactive=True)
    if not doctors:
        st.info("Список врачей пуст.")
        return

    def doctor_option_label(doctor_id: str) -> str:
        doctor = next(item for item in doctors if item["id"] == doctor_id)
        status = "" if doctor.get("is_active") != "false" else " [неактивен]"
        return f"{doctor['name']} ({doctor_id}){status}"

    selected_id = st.selectbox(
        "Редактировать врача",
        [doctor["id"] for doctor in doctors],
        format_func=doctor_option_label,
    )
    selected = next(doctor for doctor in doctors if doctor["id"] == selected_id)

    with st.form("admin_edit_doctor"):
        edit_name = st.text_input("ФИО", value=selected.get("name", ""))
        edit_specialty = st.text_input("Специальность", value=selected.get("specialty", "Эндокринолог"))
        edit_email = st.text_input("Email", value=selected.get("email", ""))
        edit_telegram = st.text_input("Telegram chat_id", value=selected.get("telegram_chat_id", ""))
        edit_password = st.text_input("Новый пароль кабинета (пусто = не менять)", type="password")
        edit_active = st.checkbox("Врач активен", value=selected.get("is_active") != "false")
        if st.form_submit_button("Сохранить изменения"):
            try:
                upsert_doctor(
                    {
                        "id": selected_id,
                        "name": edit_name.strip(),
                        "specialty": edit_specialty.strip() or "Эндокринолог",
                        "email": edit_email.strip(),
                        "telegram_chat_id": edit_telegram.strip(),
                        "password": edit_password.strip() or selected.get("password", ""),
                        "is_active": edit_active,
                    }
                )
                st.success("Данные врача сохранены.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    toggle_col1, toggle_col2 = st.columns(2)
    with toggle_col1:
        if selected.get("is_active") != "false":
            if st.button("Деактивировать врача"):
                set_doctor_active(selected_id, active=False)
                st.success("Врач деактивирован — новые пациенты не смогут выбрать его в ссылке.")
                st.rerun()
        else:
            if st.button("Снова активировать врача"):
                set_doctor_active(selected_id, active=True)
                st.success("Врач снова активен.")
                st.rerun()

    st.subheader("Ссылки для пациентов")
    web_link = patient_web_url(PUBLIC_URL, selected_id)
    web_long = patient_web_url(PUBLIC_URL, selected_id, short=False)
    bot_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=doctor_{selected_id}"
    qr_link = f"{PUBLIC_URL.rstrip('/')}/?page=qr&doctor={selected_id}"
    st.text_input("Короткая ссылка (для QR и визитки)", value=web_link, disabled=True)
    st.text_input("Полная ссылка", value=web_long, disabled=True)
    st.text_input("Telegram-бот", value=bot_link, disabled=True)
    st.markdown(f"[Страница QR для печати]({qr_link})")
    st.caption("Короткая ссылка `/d/код` работает после настройки Nginx (см. deploy/nginx-anamnes.conf.example).")

    st.subheader("QR-коды")
    qr_col1, qr_col2 = st.columns(2)
    with qr_col1:
        st.markdown("**Telegram (рекомендуется)**")
        st.image(make_qr_image(bot_link), width=200)
        st.download_button(
            "Скачать PNG (бот)",
            make_qr_image(bot_link),
            f"qr-bot-{selected_id}.png",
            "image/png",
            key=f"admin_qr_bot_{selected_id}",
        )
    with qr_col2:
        st.markdown("**Сайт**")
        st.image(make_qr_image(web_link), width=200)
        st.download_button(
            "Скачать PNG (сайт)",
            make_qr_image(web_link),
            f"qr-web-{selected_id}.png",
            "image/png",
            key=f"admin_qr_web_{selected_id}",
        )

    st.subheader("Уведомления врачу")
    for line in notification_status_lines(selected):
        st.markdown(line)
    if st.button("Отправить тестовое уведомление", key=f"test_notify_{selected_id}"):
        for ok, message in send_test_notifications(selected):
            if ok:
                st.success(message)
            else:
                st.warning(message)

    if use_postgres():
        st.download_button(
            "Скачать doctors.json (резервная копия)",
            data=json.dumps({"doctors": load_doctors(include_inactive=True)}, ensure_ascii=False, indent=2),
            file_name="doctors-backup.json",
            mime="application/json",
        )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")
    init_storage()

    if get_query_param("page") == "qr":
        doctors = load_doctors()
        doctor_id = get_query_param("doctor").strip().lower()
        doctor = get_doctor_by_id(doctors, doctor_id) if doctor_id else None
        render_qr_page(doctor, TELEGRAM_BOT_USERNAME, PUBLIC_URL)
        return

    with st.sidebar:
        st.header(APP_TITLE)
        page = st.radio("Раздел", ["Анкета пациента", "Кабинет врача", "Управление врачами"])
        st.divider()
        if use_postgres():
            st.caption("База: PostgreSQL")
        else:
            st.caption("База: JSON-файлы")
        st.caption("Не используйте реальные данные без HTTPS и настроенного доступа.")

    if page == "Анкета пациента":
        render_patient_form()
    elif page == "Кабинет врача":
        render_doctor_dashboard()
    else:
        render_admin_panel()


if __name__ == "__main__":
    main()
