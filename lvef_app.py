"""Streamlit app: LVEF estimation and clinical prediction."""

from __future__ import annotations

import streamlit as st

from clinical.lvef import (
    LvefComparison,
    LvefEstimate,
    compare_simpson_and_teichholz,
    estimate_lvef_from_fs_only,
    estimate_lvef_simpson,
    estimate_lvef_teichholz,
    predict_reduced_lvef_clinical,
)
from clinical.pdf_export import build_text_pdf
from clinical.report_text import (
    format_lvef_clinical_report,
    format_lvef_comparison_report,
    format_lvef_echo_report,
)

APP_TITLE = "Прогнозирование фракции выброса левого желудочка (ФВ ЛЖ)"

METHODS = {
    "simpson": "Симпсон — по конечным объёмам (КДО/КСО)",
    "teichholz": "Teichholz — по LVIDd и LVIDs",
    "fs": "Фракция укорочения (FS)",
    "compare": "Сравнение Симпсон vs Teichholz",
    "clinical": "Клинический прогноз сниженной ФВ",
}


def pdf_download_button(title: str, body: str, filename: str) -> None:
    st.download_button(
        "Скачать PDF",
        data=build_text_pdf(body, title),
        file_name=filename,
        mime="application/pdf",
    )


def render_echo_result(result: LvefEstimate, author: str, patient_ref: str) -> None:
    st.success(f"Расчётная ФВ ЛЖ: **{result.lvef_percent}%**")
    st.info(f"Интерпретация: {result.category_label}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Метод", result.method)
    if result.edv_ml is not None:
        c2.metric("КДО", f"{result.edv_ml} мл")
    if result.esv_ml is not None:
        c3.metric("КСО", f"{result.esv_ml} мл")
    if result.fractional_shortening_percent is not None:
        st.metric("Фракция укорочения (FS)", f"{result.fractional_shortening_percent}%")

    for note in result.notes:
        st.caption(f"• {note}")

    pdf_download_button(
        "Оценка ФВ ЛЖ",
        format_lvef_echo_report(result, author=author, patient_ref=patient_ref),
        "lvef_report.pdf",
    )


def render_comparison_result(comparison: LvefComparison, author: str) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Симпсон", f"{comparison.simpson.lvef_percent}%")
    c2.metric("Teichholz", f"{comparison.teichholz.lvef_percent}%")
    c3.metric("Расхождение", f"{comparison.difference_percent} п.п.")

    if comparison.consistent:
        st.success("Методы согласуются (расхождение ≤10 п.п.)")
    else:
        st.warning("Значимое расхождение — проверьте качество измерений и асинергию")

    st.info(comparison.recommendation)
    pdf_download_button(
        "Сравнение методов ФВ ЛЖ",
        format_lvef_comparison_report(comparison, author=author),
        "lvef_comparison.pdf",
    )


def render_clinical_result(result, author: str) -> None:
    st.success(f"Вероятность сниженной ФВ (<50%): **{result.probability_reduced_lvef_percent:.0f}%**")
    st.info(f"Клинический риск: {result.risk_label} (балл {result.score})")
    st.write("Учтённые факторы:")
    for factor in result.factors:
        st.write(f"- {factor}")
    st.caption(
        "Ориентировочная оценка до выполнения ЭхоКГ. "
        "Для диагностики сердечной недостаточности нужна визуализация и клинический контекст."
    )
    pdf_download_button(
        "Клинический прогноз ФВ ЛЖ",
        format_lvef_clinical_report(result, author=author),
        "lvef_clinical_risk.pdf",
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="❤️", layout="wide")
    st.title(APP_TITLE)
    st.caption("Оценка и прогнозирование ФВ ЛЖ по данным ЭхоКГ и клиническим факторам")

    with st.sidebar:
        st.header("Метод")
        method = st.radio(
            "Выберите метод",
            list(METHODS.keys()),
            format_func=lambda key: METHODS[key],
        )
        st.divider()
        author = st.text_input("ФИО исполнителя (для PDF)", value="")
        patient_ref = st.text_input("ID пациента / исследования", value="")
        st.caption("Сервис: ikorsakov.tech:9999")
        st.caption("Не заменяет официальное заключение ЭхоКГ.")

    if method == "simpson":
        st.subheader("Метод Симпона (биапикальные объёмы)")
        c1, c2 = st.columns(2)
        edv = c1.number_input("КДО, мл", min_value=1.0, value=120.0, step=1.0)
        esv = c2.number_input("КСО, мл", min_value=0.0, value=45.0, step=1.0)
        if st.button("Рассчитать ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_simpson(edv, esv), author, patient_ref)
            except ValueError as exc:
                st.error(str(exc))

    elif method == "teichholz":
        st.subheader("Метод Teichholz")
        c1, c2 = st.columns(2)
        lvidd = c1.number_input("LVIDd, мм", min_value=1.0, value=50.0, step=0.5)
        lvids = c2.number_input("LVIDs, мм", min_value=1.0, value=32.0, step=0.5)
        if st.button("Рассчитать ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_teichholz(lvidd, lvids), author, patient_ref)
            except ValueError as exc:
                st.error(str(exc))

    elif method == "fs":
        st.subheader("Фракция укорочения")
        c1, c2 = st.columns(2)
        lvidd = c1.number_input("LVIDd, мм", min_value=1.0, value=50.0, step=0.5)
        lvids = c2.number_input("LVIDs, мм", min_value=1.0, value=32.0, step=0.5)
        if st.button("Оценить ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_from_fs_only(lvidd, lvids), author, patient_ref)
            except ValueError as exc:
                st.error(str(exc))

    elif method == "compare":
        st.subheader("Сравнение методов")
        st.caption("Введите объёмы и линейные размеры из одного исследования.")
        c1, c2 = st.columns(2)
        edv = c1.number_input("КДО, мл", min_value=1.0, value=120.0, step=1.0, key="cmp_edv")
        esv = c1.number_input("КСО, мл", min_value=0.0, value=45.0, step=1.0, key="cmp_esv")
        lvidd = c2.number_input("LVIDd, мм", min_value=1.0, value=50.0, step=0.5, key="cmp_lvidd")
        lvids = c2.number_input("LVIDs, мм", min_value=1.0, value=32.0, step=0.5, key="cmp_lvids")
        if st.button("Сравнить методы", type="primary"):
            try:
                render_comparison_result(
                    compare_simpson_and_teichholz(edv, esv, lvidd, lvids),
                    author,
                )
            except ValueError as exc:
                st.error(str(exc))

    else:
        st.subheader("Клинический прогноз сниженной ФВ")
        c1, c2 = st.columns(2)
        with c1:
            age = st.number_input("Возраст, лет", min_value=18, max_value=110, value=65)
            male = st.checkbox("Мужской пол")
            prior_mi = st.checkbox("Перенесённый инфаркт миокарда")
            diabetes = st.checkbox("Сахарный диабет")
            dyspnea = st.checkbox("Одышка при нагрузке")
        with c2:
            atrial_fibrillation = st.checkbox("Фибрилляция предсердий")
            hypertension = st.checkbox("Артериальная гипертония")
            peripheral_edema = st.checkbox("Отёки нижних конечностей")
            qrs_ms = st.number_input("Длительность QRS, мс", min_value=40, max_value=300, value=95)
            nt_probnp = st.number_input(
                "NT-proBNP, пг/мл (опционально)",
                min_value=0.0,
                value=0.0,
                help="Оставьте 0, если неизвестно.",
            )

        if st.button("Рассчитать риск", type="primary"):
            try:
                render_clinical_result(
                    predict_reduced_lvef_clinical(
                        age=int(age),
                        male=male,
                        prior_mi=prior_mi,
                        diabetes=diabetes,
                        atrial_fibrillation=atrial_fibrillation,
                        qrs_ms=int(qrs_ms),
                        nt_probnp_pg_ml=None if nt_probnp <= 0 else float(nt_probnp),
                        hypertension=hypertension,
                        dyspnea=dyspnea,
                        peripheral_edema=peripheral_edema,
                    ),
                    author,
                )
            except ValueError as exc:
                st.error(str(exc))

    with st.expander("Справка"):
        st.markdown(
            """
            ### Нормы и категории ФВ ЛЖ

            | ФВ ЛЖ | Категория |
            |-------|-----------|
            | ≥55% | Норма |
            | 41–54% | Незначительно снижена |
            | 30–40% | Умеренно снижена |
            | <30% | Выраженно снижена |

            ### Методы
            - **Симпсон** — расчёт по конечным объёмам (предпочтительно).
            - **Teichholz** — оценка по линейным размерам.
            - **FS** — быстрая оценка у постели больного.
            - **Сравнение** — контроль согласованности методов.
            - **Клинический прогноз** — вероятность сниженной ФВ до ЭхоКГ.

            Результат носит вспомогательный характер и требует клинической интерпретации врачом.
            """
        )


if __name__ == "__main__":
    main()
