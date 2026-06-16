"""Sample size calculations for common clinical trial designs."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log
from typing import Literal

from scipy import stats
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize


Alternative = Literal["two-sided", "larger", "smaller"]


@dataclass(frozen=True)
class SampleSizeResult:
    design: str
    n_per_group_control: int
    n_per_group_treatment: int
    n_total: int
    n_total_with_dropout: int
    alpha: float
    power: float
    allocation_ratio: float
    dropout_rate: float
    details: dict[str, float | str]


def _round_up_group_sizes(n_control: float, ratio: float) -> tuple[int, int, int]:
    n1 = max(1, ceil(n_control))
    n2 = max(1, ceil(n1 * ratio))
    return n1, n2, n1 + n2


def _apply_dropout(n_total: int, dropout_rate: float) -> int:
    if dropout_rate <= 0:
        return n_total
    if dropout_rate >= 1:
        raise ValueError("Доля выбывания должна быть меньше 1.")
    return ceil(n_total / (1 - dropout_rate))


def _z_values(alpha: float, power: float, *, two_sided: bool = True) -> tuple[float, float]:
    if not 0 < alpha < 1:
        raise ValueError("Уровень значимости α должен быть между 0 и 1.")
    if not 0 < power < 1:
        raise ValueError("Мощность должна быть между 0 и 1.")
    z_alpha = stats.norm.ppf(1 - alpha / 2 if two_sided else 1 - alpha)
    z_beta = stats.norm.ppf(power)
    return z_alpha, z_beta


def sample_size_two_means(
    mean_control: float,
    mean_treatment: float,
    sd: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
    allocation_ratio: float = 1.0,
    alternative: Alternative = "two-sided",
    dropout_rate: float = 0.0,
) -> SampleSizeResult:
    """Two-sample t-test for continuous endpoints (superiority)."""
    if sd <= 0:
        raise ValueError("Стандартное отклонение должно быть больше 0.")
    if allocation_ratio <= 0:
        raise ValueError("Соотношение рандомизации должно быть больше 0.")

    effect_size = abs(mean_treatment - mean_control) / sd
    if effect_size == 0:
        raise ValueError("Разница средних не может быть равна 0.")

    analysis = TTestIndPower()
    n_control = analysis.solve_power(
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        ratio=allocation_ratio,
        alternative=alternative,
    )
    n1, n2, n_total = _round_up_group_sizes(n_control, allocation_ratio)

    return SampleSizeResult(
        design="Сравнение средних (две независимые группы)",
        n_per_group_control=n1,
        n_per_group_treatment=n2,
        n_total=n_total,
        n_total_with_dropout=_apply_dropout(n_total, dropout_rate),
        alpha=alpha,
        power=power,
        allocation_ratio=allocation_ratio,
        dropout_rate=dropout_rate,
        details={
            "mean_control": mean_control,
            "mean_treatment": mean_treatment,
            "sd": sd,
            "absolute_difference": abs(mean_treatment - mean_control),
            "cohens_d": effect_size,
            "alternative": alternative,
        },
    )


def sample_size_two_proportions(
    p_control: float,
    p_treatment: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
    allocation_ratio: float = 1.0,
    alternative: Alternative = "two-sided",
    dropout_rate: float = 0.0,
) -> SampleSizeResult:
    """Two-sample comparison of proportions (superiority)."""
    for label, value in (("Контроль", p_control), ("Лечение", p_treatment)):
        if not 0 < value < 1:
            raise ValueError(f"Доля для группы «{label}» должна быть между 0 и 1.")
    if p_control == p_treatment:
        raise ValueError("Доли в группах не должны совпадать.")
    if allocation_ratio <= 0:
        raise ValueError("Соотношение рандомизации должно быть больше 0.")

    effect_size = abs(proportion_effectsize(p_control, p_treatment))
    analysis = NormalIndPower()
    n_control = analysis.solve_power(
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        ratio=allocation_ratio,
        alternative=alternative,
    )
    n1, n2, n_total = _round_up_group_sizes(n_control, allocation_ratio)

    return SampleSizeResult(
        design="Сравнение долей (две независимые группы)",
        n_per_group_control=n1,
        n_per_group_treatment=n2,
        n_total=n_total,
        n_total_with_dropout=_apply_dropout(n_total, dropout_rate),
        alpha=alpha,
        power=power,
        allocation_ratio=allocation_ratio,
        dropout_rate=dropout_rate,
        details={
            "p_control": p_control,
            "p_treatment": p_treatment,
            "absolute_difference": abs(p_treatment - p_control),
            "relative_risk": p_treatment / p_control if p_control > 0 else float("nan"),
            "cohens_h": float(effect_size),
            "alternative": alternative,
        },
    )


def sample_size_noninferiority_proportions(
    p_control: float,
    p_treatment: float,
    margin: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
    allocation_ratio: float = 1.0,
    dropout_rate: float = 0.0,
) -> SampleSizeResult:
    """Non-inferiority for proportions (one-sided, delta margin)."""
    if not 0 < p_control < 1 or not 0 < p_treatment < 1:
        raise ValueError("Доли должны быть между 0 и 1.")
    if margin <= 0:
        raise ValueError("Непревосходящая граница (margin) должна быть больше 0.")
    if allocation_ratio <= 0:
        raise ValueError("Соотношение рандомизации должно быть больше 0.")

    expected_diff = p_treatment - p_control + margin
    if expected_diff <= 0:
        raise ValueError("Ожидаемая разница с учётом margin должна быть положительной.")

    z_alpha, z_beta = _z_values(alpha, power, two_sided=False)
    variance_term = p_control * (1 - p_control) + p_treatment * (1 - p_treatment) / allocation_ratio
    n_control = ((z_alpha + z_beta) ** 2) * variance_term / (expected_diff**2)
    n1, n2, n_total = _round_up_group_sizes(n_control, allocation_ratio)

    return SampleSizeResult(
        design="Непревосходство по доле (non-inferiority)",
        n_per_group_control=n1,
        n_per_group_treatment=n2,
        n_total=n_total,
        n_total_with_dropout=_apply_dropout(n_total, dropout_rate),
        alpha=alpha,
        power=power,
        allocation_ratio=allocation_ratio,
        dropout_rate=dropout_rate,
        details={
            "p_control": p_control,
            "p_treatment": p_treatment,
            "margin": margin,
            "observed_difference": p_treatment - p_control,
            "alternative": "non-inferiority (one-sided)",
        },
    )


def sample_size_survival(
    hazard_ratio: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
    allocation_ratio: float = 1.0,
    dropout_rate: float = 0.0,
    event_rate: float = 0.5,
) -> SampleSizeResult:
    """Simplified Schoenfeld formula for time-to-event endpoints."""
    if hazard_ratio <= 0:
        raise ValueError("Отношение рисков (HR) должно быть больше 0.")
    if hazard_ratio == 1:
        raise ValueError("HR не может быть равно 1.")
    if not 0 < event_rate < 1:
        raise ValueError("Ожидаемая доля событий должна быть между 0 и 1.")
    if allocation_ratio <= 0:
        raise ValueError("Соотношение рандомизации должно быть больше 0.")

    z_alpha, z_beta = _z_values(alpha, power, two_sided=True)
    r = allocation_ratio
    log_hr = abs(log(hazard_ratio))
    events_required = ceil(((z_alpha + z_beta) ** 2) * ((1 + r) ** 2) / (r * (log_hr**2)))
    n_total = ceil(events_required / event_rate)
    n1, n2, _ = _round_up_group_sizes(n_total / (1 + allocation_ratio), allocation_ratio)

    return SampleSizeResult(
        design="Время до события (log-rank, формула Schoenfeld)",
        n_per_group_control=n1,
        n_per_group_treatment=n2,
        n_total=n1 + n2,
        n_total_with_dropout=_apply_dropout(n1 + n2, dropout_rate),
        alpha=alpha,
        power=power,
        allocation_ratio=allocation_ratio,
        dropout_rate=dropout_rate,
        details={
            "hazard_ratio": hazard_ratio,
            "events_required": float(events_required),
            "event_rate": event_rate,
            "alternative": "two-sided",
        },
    )
