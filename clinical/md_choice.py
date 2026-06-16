"""MD Choice: T2DM drug choice prediction (ML-based CDSS)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sklearn.ensemble import RandomForestClassifier

DRUG_CLASSES = [
    "Метформин",
    "иНГЛТ-2 (SGLT2)",
    "аГПП-1 (GLP-1)",
    "иППП-4 (DPP-4)",
    "Сульфонилмочевины",
    "Инсулин",
]


@dataclass(frozen=True)
class PatientProfile:
    age: int
    bmi: float
    hba1c: float
    egfr: float
    diabetes_years: int
    has_cvd: bool
    has_heart_failure: bool
    needs_weight_loss: bool
    hypoglycemia_risk: bool
    on_metformin: bool
    on_insulin: bool


@dataclass(frozen=True)
class DrugRecommendation:
    drug_class: str
    probability: float
    score: int
    rationale: list[str]


@dataclass(frozen=True)
class MdChoiceResult:
    primary: DrugRecommendation
    alternatives: list[DrugRecommendation]
    warnings: list[str]
    model_name: str


def _guideline_label(
    age: int,
    bmi: float,
    hba1c: float,
    egfr: float,
    has_cvd: bool,
    has_hf: bool,
    needs_weight_loss: bool,
    hypoglycemia_risk: bool,
    on_metformin: bool,
    on_insulin: bool,
) -> int:
    if on_insulin or hba1c >= 10.0:
        return 5  # insulin
    if egfr < 30:
        return 5
    if not on_metformin and egfr >= 30:
        return 0  # metformin first
    if has_hf or (has_cvd and egfr >= 30):
        return 1  # sglt2
    if needs_weight_loss or bmi >= 30 or hba1c >= 8.0:
        return 2  # glp1
    if hypoglycemia_risk or age >= 70:
        return 3  # dpp4
    if hba1c >= 7.5:
        return 1
    return 3


def _profile_to_features(profile: PatientProfile) -> np.ndarray:
    return np.array(
        [
            profile.age,
            profile.bmi,
            profile.hba1c,
            profile.egfr,
            float(profile.has_cvd),
            float(profile.has_heart_failure),
            float(profile.needs_weight_loss),
            float(profile.hypoglycemia_risk),
            float(profile.on_metformin),
            float(profile.on_insulin),
            profile.diabetes_years,
        ],
        dtype=float,
    )


@lru_cache(maxsize=1)
def _load_model() -> RandomForestClassifier:
    rng = np.random.default_rng(42)
    rows = []
    labels = []
    for _ in range(4000):
        age = int(rng.integers(35, 85))
        bmi = float(rng.uniform(22, 42))
        hba1c = float(rng.uniform(6.5, 12.0))
        egfr = float(rng.uniform(25, 110))
        years = int(rng.integers(0, 25))
        has_cvd = bool(rng.random() < 0.25)
        has_hf = bool(rng.random() < 0.12)
        needs_wl = bool(bmi >= 27 or rng.random() < 0.35)
        hypo = bool(age >= 70 or rng.random() < 0.2)
        on_met = bool(rng.random() < 0.7)
        on_ins = bool(hba1c >= 9.5 and rng.random() < 0.4)
        profile = PatientProfile(
            age=age,
            bmi=bmi,
            hba1c=hba1c,
            egfr=egfr,
            diabetes_years=years,
            has_cvd=has_cvd,
            has_heart_failure=has_hf,
            needs_weight_loss=needs_wl,
            hypoglycemia_risk=hypo,
            on_metformin=on_met,
            on_insulin=on_ins,
        )
        rows.append(_profile_to_features(profile))
        labels.append(
            _guideline_label(
                age, bmi, hba1c, egfr, has_cvd, has_hf, needs_wl, hypo, on_met, on_ins
            )
        )
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(np.vstack(rows), np.array(labels))
    return model


def _build_rationale(drug_index: int, profile: PatientProfile) -> list[str]:
    reasons: list[str] = []
    drug = DRUG_CLASSES[drug_index]
    if drug_index == 0:
        reasons.append("Базовая терапия при СД2 при достаточной функции почек.")
    if drug_index == 1:
        if profile.has_heart_failure:
            reasons.append("Сердечная недостаточность — приоритет иНГЛТ-2.")
        if profile.has_cvd:
            reasons.append("Сердечно-сосудистые события — иНГЛТ-2 с доказанной пользой.")
    if drug_index == 2:
        if profile.bmi >= 27 or profile.needs_weight_loss:
            reasons.append("Избыточный вес — аГПП-1 способствует снижению массы тела.")
        if profile.hba1c >= 8.0:
            reasons.append("Выраженная гипергликемия — высокая эффективность аГПП-1.")
    if drug_index == 3:
        if profile.hypoglycemia_risk or profile.age >= 70:
            reasons.append("Низкий риск гипогликемии по сравнению с сульфонилмочевиной.")
    if drug_index == 4:
        reasons.append("Возможен вариант при отсутствии противопоказаний и низком риске гипогликемии.")
    if drug_index == 5:
        if profile.hba1c >= 9.0:
            reasons.append("Выраженная декомпенсация гликемии.")
        if profile.on_insulin:
            reasons.append("Пациент уже на инсулинотерапии — титрация/оптимизация.")
    if not reasons:
        reasons.append("Соответствует профилю пациента по данным модели.")
    return reasons


def _warnings(profile: PatientProfile) -> list[str]:
    items: list[str] = []
    if profile.egfr < 30:
        items.append("рСКФ <30 мл/мин — метформин противопоказан; осторожность с иНГЛТ-2.")
    elif profile.egfr < 45:
        items.append("рСКФ 30–44 — ограничение дозы метформина.")
    if profile.has_heart_failure and profile.egfr < 20:
        items.append("Тяжёлая ХСН при низкой рСКФ — индивидуальная оценка иНГЛТ-2.")
    if profile.hypoglycemia_risk:
        items.append("Повышенный риск гипогликемии — избегать сульфонилмочевин без веских причин.")
    return items


def predict_drug_choice(profile: PatientProfile) -> MdChoiceResult:
    if profile.age < 18:
        raise ValueError("Возраст должен быть ≥18 лет.")
    if profile.bmi <= 0:
        raise ValueError("ИМТ должен быть больше 0.")
    if profile.egfr <= 0:
        raise ValueError("рСКФ должна быть больше 0.")

    model = _load_model()
    features = _profile_to_features(profile).reshape(1, -1)
    probabilities = model.predict_proba(features)[0]
    classes = model.classes_

    ranked = sorted(
        [
            DrugRecommendation(
                drug_class=DRUG_CLASSES[int(cls)],
                probability=float(probabilities[i]),
                score=int(round(probabilities[i] * 100)),
                rationale=_build_rationale(int(cls), profile),
            )
            for i, cls in enumerate(classes)
        ],
        key=lambda item: item.probability,
        reverse=True,
    )

    return MdChoiceResult(
        primary=ranked[0],
        alternatives=ranked[1:4],
        warnings=_warnings(profile),
        model_name="RandomForest (обучение на клинически размеченном синтетическом датасете)",
    )
