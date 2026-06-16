"""Text formatters for PDF export."""

from __future__ import annotations

from datetime import datetime, timezone

from clinical.lvef import ClinicalHfRisk, LvefComparison, LvefEstimate
from clinical.sample_size import SampleSizeResult


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_sample_size_report(result: SampleSizeResult, *, author: str = "") -> str:
    lines = [
        f"Дата расчёта: {_timestamp()}",
        f"Сервис: ikorsakov.tech:8080",
    ]
    if author.strip():
        lines.append(f"Исполнитель: {author.strip()}")
    lines.extend(
        [
            "",
            "РАСЧЁТ РАЗМЕРА ВЫБОРКИ",
            f"Дизайн: {result.design}",
            "",
            "ИТОГ",
            f"- Контроль: {result.n_per_group_control}",
            f"- Лечение: {result.n_per_group_treatment}",
            f"- Всего: {result.n_total}",
            f"- С учётом выбывания ({result.dropout_rate:.0%}): {result.n_total_with_dropout}",
            "",
            "ПАРАМЕТРЫ",
            f"- α: {result.alpha:.3f}",
            f"- Мощность: {result.power:.0%}",
            f"- Рандомизация (лечение/контроль): {result.allocation_ratio:g}",
            "",
            "ДЕТАЛИ",
        ]
    )
    for key, value in result.details.items():
        if isinstance(value, float):
            lines.append(f"- {key}: {value:.4g}")
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "ПРИМЕЧАНИЕ: ориентировочный расчёт. Финальный размер выборки утверждает биостатистик протокола.",
        ]
    )
    return "\n".join(lines)


def format_lvef_echo_report(result: LvefEstimate, *, author: str = "", patient_ref: str = "") -> str:
    lines = [
        f"Дата расчёта: {_timestamp()}",
        f"Сервис: ikorsakov.tech:9999",
    ]
    if author.strip():
        lines.append(f"Исполнитель: {author.strip()}")
    if patient_ref.strip():
        lines.append(f"Идентификатор: {patient_ref.strip()}")
    lines.extend(
        [
            "",
            "ОЦЕНКА ФВ ЛЖ",
            f"Метод: {result.method}",
            f"ФВ ЛЖ: {result.lvef_percent}%",
            f"Интерпретация: {result.category_label}",
        ]
    )
    if result.edv_ml is not None:
        lines.append(f"КДО: {result.edv_ml} мл")
    if result.esv_ml is not None:
        lines.append(f"КСО: {result.esv_ml} мл")
    if result.fractional_shortening_percent is not None:
        lines.append(f"Фракция укорочения: {result.fractional_shortening_percent}%")
    lines.append("")
    lines.append("ПРИМЕЧАНИЯ")
    for note in result.notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("Не заменяет официальное заключение ЭхоКГ.")
    return "\n".join(lines)


def format_lvef_clinical_report(result: ClinicalHfRisk, *, author: str = "") -> str:
    lines = [
        f"Дата расчёта: {_timestamp()}",
        f"Сервис: ikorsakov.tech:9999",
    ]
    if author.strip():
        lines.append(f"Исполнитель: {author.strip()}")
    lines.extend(
        [
            "",
            "КЛИНИЧЕСКИЙ ПРОГНОЗ СНИЖЕННОЙ ФВ",
            f"Вероятность ФВ <50%: {result.probability_reduced_lvef_percent:.0f}%",
            f"Уровень риска: {result.risk_label}",
            f"Балл: {result.score}",
            "",
            "ФАКТОРЫ",
        ]
    )
    for factor in result.factors:
        lines.append(f"- {factor}")
    lines.extend(
        [
            "",
            "Ориентировочная оценка до ЭхоКГ. Требуется клиническая интерпретация кардиологом.",
        ]
    )
    return "\n".join(lines)


def format_lvef_comparison_report(comparison: LvefComparison, *, author: str = "") -> str:
    lines = [
        f"Дата расчёта: {_timestamp()}",
        f"Сервис: ikorsakov.tech:9999",
    ]
    if author.strip():
        lines.append(f"Исполнитель: {author.strip()}")
    lines.extend(
        [
            "",
            "СРАВНЕНИЕ МЕТОДОВ ФВ ЛЖ",
            f"Симпсон: {comparison.simpson.lvef_percent}% ({comparison.simpson.category_label})",
            f"Teichholz: {comparison.teichholz.lvef_percent}% ({comparison.teichholz.category_label})",
            f"Расхождение: {comparison.difference_percent} п.п.",
            f"Согласованность: {'да' if comparison.consistent else 'нет'}",
            "",
            "РЕКОМЕНДАЦИЯ",
            comparison.recommendation,
        ]
    )
    return "\n".join(lines)
