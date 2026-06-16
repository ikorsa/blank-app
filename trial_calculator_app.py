"""Streamlit app: clinical trials sample size calculator."""

from __future__ import annotations

import streamlit as st

from clinical.sample_size import (
    SampleSizeResult,
    sample_size_noninferiority_proportions,
    sample_size_survival,
    sample_size_two_means,
    sample_size_two_proportions,
)

APP_TITLE = "Калькулятор выборки для клинических испытаний"

DESIGN_OPTIONS = {
    "means": "Сравнение средних (непрерывная конечная точка)",
    "proportions": "Сравнение долей (бинарная конечная точка)",
    "noninferiority": "Непревосходство по доле (non-inferiority)",
    "survival": "Время до события (выживаемость, log-rank)",
}


def render_common_parameters() -> dict:
    st.subheader("Общие параметры")
    col1, col2, col3 = st.columns(3)
    with col1:
        alpha = st.number_input(
            "Уровень значимости α",
            min_value=0.001,
            max_value=0.2,
            value=0.05,
            step=0.005,
            format="%.3f",
            help="Обычно 0.05 (двусторонний тест).",
        )
    with col2:
        power = st.number_input(
            "Мощность (1 − β)",
            min_value=0.5,
            max_value=0.99,
            value=0.80,
            step=0.05,
            format="%.2f",
            help="Обычно 0.80 или 0.90.",
        )
    with col3:
        allocation_ratio = st.number_input(
            "Соотношение рандомизации (лечение / контроль)",
            min_value=0.1,
            max_value=5.0,
            value=1.0,
            step=0.1,
            help="1.0 = 1:1, 2.0 = 2:1 в пользу активной группы.",
        )

    dropout_pct = st.slider(
        "Ожидаемая доля выбывания, %",
        min_value=0,
        max_value=50,
        value=10,
        step=1,
        help="К итоговой выборке будет добавлен запас на выбывание.",
    )
    dropout_rate = dropout_pct / 100

    return {
        "alpha": alpha,
        "power": power,
        "allocation_ratio": allocation_ratio,
        "dropout_rate": dropout_rate,
    }


def render_result(result: SampleSizeResult) -> None:
    st.success("Расчёт выполнен")
    c1, c2, c3 = st.columns(3)
    c1.metric("Контроль", result.n_per_group_control)
    c2.metric("Лечение", result.n_per_group_treatment)
    c3.metric("Всего", result.n_total)

    if result.dropout_rate > 0:
        st.metric(
            "С учётом выбывания",
            result.n_total_with_dropout,
            help=f"Запас на выбывание {result.dropout_rate:.0%}",
        )

    with st.expander("Параметры расчёта", expanded=False):
        st.write(f"**Дизайн:** {result.design}")
        st.write(f"**α:** {result.alpha:.3f}, **мощность:** {result.power:.0%}, **рандомизация:** 1:{result.allocation_ratio:g}")
        for key, value in result.details.items():
            if isinstance(value, float):
                st.write(f"- {key}: {value:.4g}")
            else:
                st.write(f"- {key}: {value}")


def calculate(design: str, common: dict) -> SampleSizeResult | None:
    try:
        if design == "means":
            st.subheader("Параметры конечной точки")
            c1, c2, c3 = st.columns(3)
            mean_control = c1.number_input("Среднее в контроле", value=10.0, format="%.3f")
            mean_treatment = c2.number_input("Среднее в группе лечения", value=12.0, format="%.3f")
            sd = c3.number_input("Стандартное отклонение (общее)", min_value=0.001, value=4.0, format="%.3f")
            alternative = st.selectbox(
                "Альтернатива",
                ["two-sided", "larger", "smaller"],
                format_func=lambda x: {
                    "two-sided": "Двусторонняя",
                    "larger": "Односторонняя: лечение лучше",
                    "smaller": "Односторонняя: лечение хуже",
                }[x],
            )
            if st.button("Рассчитать выборку", type="primary"):
                return sample_size_two_means(
                    mean_control,
                    mean_treatment,
                    sd,
                    alpha=common["alpha"],
                    power=common["power"],
                    allocation_ratio=common["allocation_ratio"],
                    alternative=alternative,
                    dropout_rate=common["dropout_rate"],
                )

        if design == "proportions":
            st.subheader("Параметры конечной точки")
            c1, c2 = st.columns(2)
            p_control = c1.number_input("Доля в контроле", min_value=0.001, max_value=0.999, value=0.30, format="%.3f")
            p_treatment = c2.number_input("Доля в группе лечения", min_value=0.001, max_value=0.999, value=0.50, format="%.3f")
            alternative = st.selectbox(
                "Альтернатива",
                ["two-sided", "larger", "smaller"],
                format_func=lambda x: {
                    "two-sided": "Двусторонняя",
                    "larger": "Односторонняя: лечение лучше",
                    "smaller": "Односторонняя: лечение хуже",
                }[x],
            )
            if st.button("Рассчитать выборку", type="primary"):
                return sample_size_two_proportions(
                    p_control,
                    p_treatment,
                    alpha=common["alpha"],
                    power=common["power"],
                    allocation_ratio=common["allocation_ratio"],
                    alternative=alternative,
                    dropout_rate=common["dropout_rate"],
                )

        if design == "noninferiority":
            st.subheader("Параметры непревосходства")
            st.caption("Односторонний тест: активное лечение не хуже контроля более чем на заданную границу (margin).")
            c1, c2, c3 = st.columns(3)
            p_control = c1.number_input("Доля в контроле", min_value=0.001, max_value=0.999, value=0.80, format="%.3f")
            p_treatment = c2.number_input("Ожидаемая доля в лечении", min_value=0.001, max_value=0.999, value=0.82, format="%.3f")
            margin = c3.number_input("Непревосходящая граница (margin)", min_value=0.001, max_value=0.5, value=0.10, format="%.3f")
            if st.button("Рассчитать выборку", type="primary"):
                return sample_size_noninferiority_proportions(
                    p_control,
                    p_treatment,
                    margin,
                    alpha=common["alpha"],
                    power=common["power"],
                    allocation_ratio=common["allocation_ratio"],
                    dropout_rate=common["dropout_rate"],
                )

        if design == "survival":
            st.subheader("Параметры выживаемости")
            c1, c2 = st.columns(2)
            hazard_ratio = c1.number_input(
                "Отношение рисков (HR)",
                min_value=0.01,
                max_value=5.0,
                value=0.70,
                step=0.05,
                help="HR < 1 — снижение риска в группе лечения.",
            )
            event_rate = c2.number_input(
                "Ожидаемая доля событий",
                min_value=0.05,
                max_value=0.95,
                value=0.45,
                step=0.05,
                help="Доля пациентов с событием к концу наблюдения.",
            )
            if st.button("Рассчитать выборку", type="primary"):
                return sample_size_survival(
                    hazard_ratio,
                    alpha=common["alpha"],
                    power=common["power"],
                    allocation_ratio=common["allocation_ratio"],
                    dropout_rate=common["dropout_rate"],
                    event_rate=event_rate,
                )
    except ValueError as exc:
        st.error(str(exc))
    return None


def render_methodology() -> None:
    st.markdown(
        """
        ### Методология

        Калькулятор предназначен для **предварительного** планирования клинических исследований.
        Итоговый размер выборки должен подтверждаться биостатистиком с учётом дизайна протокола.

        | Дизайн | Метод |
        |--------|-------|
        | Сравнение средних | Двухвыборочный t-критерий, размер эффекта Cohen's d |
        | Сравнение долей | Z-тест для двух пропорций, Cohen's h |
        | Непревосходство | Односторонний z-тест с margin |
        | Выживаемость | Формула Schoenfeld для log-rank |

        **Рекомендации:** CONSORT, ICH E9, учёт центров, промежуточных анализов и кратности сравнений
        выполняется отдельно.
        """
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
    st.title(APP_TITLE)
    st.caption("Предварительный расчёт размера выборки для клинических испытаний")

    with st.sidebar:
        st.header("Дизайн исследования")
        design = st.radio(
            "Тип конечной точки",
            list(DESIGN_OPTIONS.keys()),
            format_func=lambda key: DESIGN_OPTIONS[key],
        )
        st.divider()
        st.caption("Сервис: ikorsakov.tech:8080")
        st.caption("Результат носит ориентировочный характер.")

    common = render_common_parameters()
    result = calculate(design, common)
    if result:
        st.divider()
        render_result(result)

    with st.expander("Справка по методологии"):
        render_methodology()


if __name__ == "__main__":
    main()
