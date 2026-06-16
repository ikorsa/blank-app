"""Streamlit app: LVEF estimation and clinical prediction."""

from __future__ import annotations

import streamlit as st

from clinical.lvef import (
    estimate_lvef_from_fs_only,
    estimate_lvef_simpson,
    estimate_lvef_teichholz,
    predict_reduced_lvef_clinical,
)

APP_TITLE = "Прогнозирование фракции выброса левого желудочка (ФВ ЛЖ)"

METHODS = {
    "simpson": "Симпсон — по конечным объёмам (КДО/КСО)",
    "teichholz": "Teichholz — по LVIDd и LVIDs",
    "fs": "Фракция укорочения (FS)",
    "clinical": "Клинический прогноз сниженной ФВ",
}


def render_echo_result(result) -> None:
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


def render_clinical_result(result) -> None:
    st.success(f"Вероятность сниженной ФВ (<50%): **{result.probability_reduced_lvef_percent:.0f}%**")
    st.info(f"Клинический риск: {result.risk_label} (балл {result.score})")
    st.write("Учтённые факторы:")
    for factor in result.factors:
        st.write(f"- {factor}")
    st.caption(
        "Ориентировочная оценка до выполнения ЭхоКГ. "
        "Для диагностики сердечной недостаточности нужна визуализация и клинический контекст."
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
        st.caption("Сервис: ikorsakov.tech:9999")
        st.caption("Не заменяет официальное заключение ЭхоКГ.")

    if method == "simpson":
        st.subheader("Метод Симпона (биапикальные объёмы)")
        c1, c2 = st.columns(2)
        edv = c1.number_input("КДО, мл", min_value=1.0, value=120.0, step=1.0)
        esv = c2.number_input("КСО, мл", min_value=0.0, value=45.0, step=1.0)
        if st.button("Рассчитать ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_simpson(edv, esv))
            except ValueError as exc:
                st.error(str(exc))

    elif method == "teichholz":
        st.subheader("Метод Teichholz")
        c1, c2 = st.columns(2)
        lvidd = c1.number_input("LVIDd, мм", min_value=1.0, value=50.0, step=0.5)
        lvids = c2.number_input("LVIDs, мм", min_value=1.0, value=32.0, step=0.5)
        if st.button("Рассчитать ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_teichholz(lvidd, lvids))
            except ValueError as exc:
                st.error(str(exc))

    elif method == "fs":
        st.subheader("Фракция укорочения")
        c1, c2 = st.columns(2)
        lvidd = c1.number_input("LVIDd, мм", min_value=1.0, value=50.0, step=0.5)
        lvids = c2.number_input("LVIDs, мм", min_value=1.0, value=32.0, step=0.5)
        if st.button("Оценить ФВ ЛЖ", type="primary"):
            try:
                render_echo_result(estimate_lvef_from_fs_only(lvidd, lvids))
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
        with c2:
            atrial_fibrillation = st.checkbox("Фибрилляция предсердий")
            hypertension = st.checkbox("Артериальная гипертония")
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
                    )
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
            - **Клинический прогноз** — вероятность сниженной ФВ до ЭхоКГ.

            Результат носит вспомогательный характер и требует клинической интерпретации врачом.
            """
        )


if __name__ == "__main__":
    main()
