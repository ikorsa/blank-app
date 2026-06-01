"""Patient questionnaire wizard (mobile-friendly steps)."""

from __future__ import annotations

import io
from typing import Any, Callable

import streamlit as st

WIZARD_LABELS = ["Старт", "О вас", "Жалобы", "Анамнез", "Файлы", "Отправка"]
TOTAL_STEPS = len(WIZARD_LABELS) - 1  # 1..5


def init_wizard_state(*, skip_intro: bool = False) -> None:
    if "patient_wizard_step" not in st.session_state:
        st.session_state.patient_wizard_step = 1 if skip_intro else 0
    if skip_intro and st.session_state.patient_wizard_step < 1:
        st.session_state.patient_wizard_step = 1
    if "patient_submission_done" not in st.session_state:
        st.session_state.patient_submission_done = None


def render_progress_bar(step: int) -> None:
    if step < 1:
        return
    st.progress(step / TOTAL_STEPS, text=f"Шаг {step} из {TOTAL_STEPS}: {WIZARD_LABELS[step]}")


def render_intro(assigned_doctor_name: str, on_start: Callable[[], None]) -> None:
    st.subheader("Перед приёмом у эндокринолога")
    st.markdown(
        f"""
**Врач:** {assigned_doctor_name}

**Как это работает**
- Заполнение обычно занимает **10–15 минут**
- Можно **сохранить черновик** и продолжить позже по ссылке
- Анкета **не ставит диагноз** и **не назначает лечение**
- При **острых симптомах** (боль в груди, потеря сознания, сахар >20 и т.п.) — **скорая помощь**, не эта форма

**Что подготовить:** список лекарств, даты анализов, фото/PDF выписки (по желанию).
        """
    )
    if st.button("Начать анкету", type="primary", use_container_width=True):
        on_start()


def render_nav(*, back: bool = True, next_label: str = "Далее") -> tuple[bool, bool]:
    col1, col2, col3 = st.columns([1, 1, 2])
    back_clicked = col1.button("← Назад", use_container_width=True) if back else False
    next_clicked = col2.button(next_label, type="primary", use_container_width=True)
    return back_clicked, next_clicked


def render_submission_success(
    submission_id: str,
    doctor_name: str,
    *,
    on_new: Callable[[], None],
) -> None:
    st.balloons()
    st.success("Анкета успешно отправлена врачу")
    st.markdown(
        f"""
**Номер анкеты:** `{submission_id}`

**Врач:** {doctor_name}

**Что дальше**
- Приходите на приём в назначенное время
- Возьмите документы и оригиналы анализов, если есть
- **Не заполняйте анкету повторно** — врач уже получил данные
- При изменении состояния звоните в клинику, а не ждите приёма

Спасибо!
        """
    )
    if st.button("Заполнить новую анкету (другой врач)", use_container_width=True):
        on_new()


def make_qr_image(url: str) -> bytes:
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def patient_web_url(public_url: str, doctor_id: str, *, short: bool = True) -> str:
    base = public_url.rstrip("/")
    if short:
        return f"{base}/d/{doctor_id}"
    return f"{base}/?doctor={doctor_id}"


def render_qr_page(
    doctor: dict[str, str] | None,
    bot_username: str,
    public_url: str,
) -> None:
    st.title("QR для пациентов")
    if not doctor:
        st.warning("Укажите врача в ссылке: ?page=qr&doctor=ivanova")
        return

    web_url = patient_web_url(public_url, doctor["id"])
    bot_url = f"https://t.me/{bot_username.lstrip('@')}?start=doctor_{doctor['id']}"

    st.info(f"**{doctor.get('name', doctor['id'])}** — распечатайте или покажите на планшете в регистратуре.")

    tab1, tab2 = st.tabs(["Telegram-бот", "Сайт"])
    with tab1:
        st.caption("Рекомендуется: пациент сканирует и нажимает «Заполнить анкету».")
        st.image(make_qr_image(bot_url), caption=bot_url)
        st.code(bot_url)
        st.download_button("Скачать QR (бот)", make_qr_image(bot_url), f"qr-bot-{doctor['id']}.png", "image/png")
    with tab2:
        st.image(make_qr_image(web_url), caption=web_url)
        st.code(web_url)
        st.download_button("Скачать QR (сайт)", make_qr_image(web_url), f"qr-web-{doctor['id']}.png", "image/png")
