from __future__ import annotations

from typing import Any


def doctor_short_label(doctor: dict[str, str]) -> str:
    name = str(doctor.get("name") or doctor.get("id") or "Врач")
    specialty = str(doctor.get("specialty") or "").strip()
    if specialty and len(name) + len(specialty) + 3 <= 60:
        label = f"{name} · {specialty}"
    else:
        label = name
    return label[:64]


def doctors_picker_keyboard(doctors: list[dict[str, str]]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for doctor in doctors:
        rows.append([{"text": doctor_short_label(doctor), "callback_data": f"doc:{doctor['id']}"}])
    return {"inline_keyboard": rows}
