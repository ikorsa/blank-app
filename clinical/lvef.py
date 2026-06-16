"""LVEF estimation and clinical interpretation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LvefCategory = Literal["normal", "mildly_reduced", "moderately_reduced", "severely_reduced", "hyperdynamic"]


@dataclass(frozen=True)
class LvefEstimate:
    method: str
    lvef_percent: float
    edv_ml: float | None
    esv_ml: float | None
    fractional_shortening_percent: float | None
    category: LvefCategory
    category_label: str
    notes: list[str]


def teichholz_volume(lvid_cm: float) -> float:
    if lvid_cm <= 0:
        raise ValueError("Размер полости ЛЖ должен быть больше 0.")
    return (7.0 / (2.4 + lvid_cm)) * (lvid_cm**3)


def categorize_lvef(lvef_percent: float) -> tuple[LvefCategory, str]:
    if lvef_percent > 70:
        return "hyperdynamic", "Гиперкинезия (>70%)"
    if lvef_percent >= 55:
        return "normal", "Норма (≥55%)"
    if lvef_percent >= 41:
        return "mildly_reduced", "Незначительно снижена (41–54%)"
    if lvef_percent >= 30:
        return "moderately_reduced", "Умеренно снижена (30–40%)"
    return "severely_reduced", "Выраженно снижена (<30%)"


def fractional_shortening(lvidd_mm: float, lvids_mm: float) -> float:
    if lvidd_mm <= 0:
        raise ValueError("LVIDd должен быть больше 0.")
    if lvids_mm <= 0 or lvids_mm >= lvidd_mm:
        raise ValueError("LVIDs должен быть меньше LVIDd.")
    return ((lvidd_mm - lvids_mm) / lvidd_mm) * 100


def estimate_lvef_from_fractional_shortening(fs_percent: float) -> float:
    """Rough conversion used for bedside screening; not a substitute for volumetric EF."""
    return (2 * fs_percent) + 19


def estimate_lvef_simpson(edv_ml: float, esv_ml: float) -> LvefEstimate:
    if edv_ml <= 0:
        raise ValueError("КДО должно быть больше 0.")
    if esv_ml < 0:
        raise ValueError("КСО не может быть отрицательным.")
    if esv_ml >= edv_ml:
        raise ValueError("КСО должно быть меньше КДО.")

    lvef = ((edv_ml - esv_ml) / edv_ml) * 100
    category, label = categorize_lvef(lvef)
    return LvefEstimate(
        method="Симпсон (биапикальные объёмы)",
        lvef_percent=round(lvef, 1),
        edv_ml=round(edv_ml, 1),
        esv_ml=round(esv_ml, 1),
        fractional_shortening_percent=None,
        category=category,
        category_label=label,
        notes=[
            "Предпочтительный метод при качественной визуализации.",
            "Менее точен при выраженной асинергии стенки ЛЖ.",
        ],
    )


def estimate_lvef_teichholz(lvidd_mm: float, lvids_mm: float) -> LvefEstimate:
    lvidd_cm = lvidd_mm / 10
    lvids_cm = lvids_mm / 10
    edv = teichholz_volume(lvidd_cm)
    esv = teichholz_volume(lvids_cm)
    fs = fractional_shortening(lvidd_mm, lvids_mm)
    lvef = ((edv - esv) / edv) * 100
    category, label = categorize_lvef(lvef)

    return LvefEstimate(
        method="Teichholz (M-mode / 2D линейные размеры)",
        lvef_percent=round(lvef, 1),
        edv_ml=round(edv, 1),
        esv_ml=round(esv, 1),
        fractional_shortening_percent=round(fs, 1),
        category=category,
        category_label=label,
        notes=[
            "Основан на геометрических допущениях о форме ЛЖ.",
            "Осторожно интерпретировать при ИБС, аневризме, ФП и выраженной дилатации.",
        ],
    )


def estimate_lvef_from_fs_only(lvidd_mm: float, lvids_mm: float) -> LvefEstimate:
    fs = fractional_shortening(lvidd_mm, lvids_mm)
    lvef = estimate_lvef_from_fractional_shortening(fs)
    category, label = categorize_lvef(lvef)
    return LvefEstimate(
        method="Фракция укорочения (FS) с оценкой ФВ",
        lvef_percent=round(lvef, 1),
        edv_ml=None,
        esv_ml=None,
        fractional_shortening_percent=round(fs, 1),
        category=category,
        category_label=label,
        notes=[
            "ФВ оценена по приближённой формуле EF ≈ 2×FS + 19.",
            "Использовать только для быстрой ориентировки у постели больного.",
        ],
    )


@dataclass(frozen=True)
class ClinicalHfRisk:
    score: int
    risk_label: str
    probability_reduced_lvef_percent: float
    factors: list[str]


def predict_reduced_lvef_clinical(
    *,
    age: int,
    male: bool,
    prior_mi: bool,
    diabetes: bool,
    atrial_fibrillation: bool,
    qrs_ms: int,
    nt_probnp_pg_ml: float | None,
    hypertension: bool,
) -> ClinicalHfRisk:
    """Simplified clinical score for pre-test probability of reduced LVEF (<50%)."""
    if age < 18:
        raise ValueError("Возраст должен быть ≥18 лет.")
    if qrs_ms <= 0:
        raise ValueError("Длительность QRS должна быть больше 0.")

    score = 0
    factors: list[str] = []

    if age >= 75:
        score += 2
        factors.append("Возраст ≥75 лет (+2)")
    elif age >= 60:
        score += 1
        factors.append("Возраст 60–74 года (+1)")

    if male:
        score += 1
        factors.append("Мужской пол (+1)")
    if prior_mi:
        score += 3
        factors.append("Перенесённый ИМ (+3)")
    if diabetes:
        score += 1
        factors.append("Сахарный диабет (+1)")
    if atrial_fibrillation:
        score += 2
        factors.append("Фибрилляция предсердий (+2)")
    if hypertension:
        score += 1
        factors.append("Артериальная гипертония (+1)")
    if qrs_ms >= 120:
        score += 2
        factors.append("QRS ≥120 мс (+2)")
    elif qrs_ms >= 100:
        score += 1
        factors.append("QRS 100–119 мс (+1)")

    if nt_probnp_pg_ml is not None:
        if nt_probnp_pg_ml >= 1000:
            score += 3
            factors.append("NT-proBNP ≥1000 пг/мл (+3)")
        elif nt_probnp_pg_ml >= 300:
            score += 2
            factors.append("NT-proBNP 300–999 пг/мл (+2)")
        elif nt_probnp_pg_ml >= 125:
            score += 1
            factors.append("NT-proBNP 125–299 пг/мл (+1)")

    if score <= 2:
        risk_label = "Низкая"
        probability = 10.0
    elif score <= 5:
        risk_label = "Умеренная"
        probability = 30.0
    elif score <= 8:
        risk_label = "Повышенная"
        probability = 55.0
    else:
        risk_label = "Высокая"
        probability = 75.0

    return ClinicalHfRisk(
        score=score,
        risk_label=risk_label,
        probability_reduced_lvef_percent=probability,
        factors=factors or ["Значимых факторов риска не выявлено"],
    )
