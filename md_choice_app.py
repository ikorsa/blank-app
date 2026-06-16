"""Streamlit app: MD Choice — T2DM drug choice CDSS."""

from __future__ import annotations

import streamlit as st

from clinical.md_choice import PatientProfile, predict_drug_choice
from clinical.pdf_export import build_text_pdf
from clinical.report_text import format_md_choice_report

APP_TITLE = "MD Choice"
APP_SUBTITLE = "Прогнозирование выбора препарата при СД2"


def render_result(result, author: str) -> None:
    st.success(f"Рекомендуемый класс препарата: **{result.primary.drug_class}**")
    st.metric("Вероятность модели", f"{result.primary.score}%")

    st.subheader("Обоснование")
    for reason in result.primary.rationale:
        st.write(f"- {reason}")

    if result.warnings:
        st.warning("Предупреждения")
        for item in result.warnings:
            st.write(f"- {item}")

    st.subheader("Альтернативные варианты")
    for alt in result.alternatives:
        st.write(f"**{alt.drug_class}** — {alt.score}%")
        for reason in alt.rationale[:2]:
            st.caption(f"• {reason}")

    st.caption(f"Модель: {result.model_name}")
    st.download_button(
        "Скачать PDF",
        data=build_text_pdf(format_md_choice_report(result, author=author), "MD Choice — СД2"),
        file_name="md_choice_report.pdf",
        mime="application/pdf",
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="💊", layout="wide")
    st.title(APP_TITLE)
    st.subheader(APP_SUBTITLE)
    st.caption("Система поддержки принятия врачебных решений на основе машинного обучения")

    with st.sidebar:
        st.header("Пациент")
        author = st.text_input("ФИО врача (для PDF)", value="Корсаков И.Н.")
        st.caption("Сервис: ikorsakov.tech:7777")
        st.caption("Не заменяет клинические рекомендации и решение врача.")

    c1, c2, c3 = st.columns(3)
    age = c1.number_input("Возраст, лет", min_value=18, max_value=100, value=58)
    bmi = c2.number_input("ИМТ", min_value=15.0, max_value=60.0, value=31.0, step=0.1)
    hba1c = c3.number_input("HbA1c, %", min_value=5.0, max_value=14.0, value=8.2, step=0.1)

    c4, c5, c6 = st.columns(3)
    egfr = c4.number_input("рСКФ, мл/мин/1.73м²", min_value=10.0, max_value=150.0, value=78.0)
    diabetes_years = c5.number_input("Длительность СД, лет", min_value=0, max_value=50, value=6)
    needs_weight_loss = c6.checkbox("Цель — снижение веса", value=True)

    st.markdown("**Сопутствующие факторы**")
    f1, f2, f3, f4, f5 = st.columns(5)
    has_cvd = f1.checkbox("ССЗ в анамнезе")
    has_hf = f2.checkbox("Сердечная недостаточность")
    hypoglycemia_risk = f3.checkbox("Риск гипогликемии")
    on_metformin = f4.checkbox("Уже принимает метформин", value=True)
    on_insulin = f5.checkbox("Уже на инсулине")

    if st.button("Получить рекомендацию", type="primary"):
        try:
            profile = PatientProfile(
                age=int(age),
                bmi=float(bmi),
                hba1c=float(hba1c),
                egfr=float(egfr),
                diabetes_years=int(diabetes_years),
                has_cvd=has_cvd,
                has_heart_failure=has_hf,
                needs_weight_loss=needs_weight_loss,
                hypoglycemia_risk=hypoglycemia_risk,
                on_metformin=on_metformin,
                on_insulin=on_insulin,
            )
            render_result(predict_drug_choice(profile), author)
        except ValueError as exc:
            st.error(str(exc))

    with st.expander("О системе"):
        st.markdown(
            """
            **MD Choice** ранжирует классы препаратов при СД2 на основе модели Random Forest,
            обученной на клинически размеченных профилях пациентов.

            Учитываются: гликемия, функция почек, ИМТ, ССЗ, ХСН, риск гипогликемии, текущая терапия.

            Результат — **поддержка решения**, а не назначение лечения.
            """
        )


if __name__ == "__main__":
    main()
