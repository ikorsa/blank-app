from __future__ import annotations

from typing import Any, Literal

from django import forms

from .django_bootstrap import ensure_django

FieldKind = Literal["choice", "multi", "text"]


def branch_field_kind(field: forms.Field) -> FieldKind:
    if isinstance(field, forms.MultipleChoiceField):
        return "multi"
    if isinstance(field, forms.ChoiceField):
        return "choice"
    return "text"


def build_branch_queue(reasons: list[str], sex: str) -> list[dict[str, Any]]:
    ensure_django()
    from intake.branch_fields import REASON_LABELS, fields_for_reason

    queue: list[dict[str, Any]] = []
    for reason in reasons:
        if not reason:
            continue
        fields = fields_for_reason(reason, sex)
        if not fields:
            continue
        reason_label = REASON_LABELS.get(reason, reason)
        for field_name, field in fields.items():
            kind = branch_field_kind(field)
            choices: list[tuple[str, str]] = []
            if kind in {"choice", "multi"}:
                raw = getattr(field, "choices", None) or []
                choices = [(str(code), str(label)) for code, label in raw if str(code)]
            queue.append(
                {
                    "reason": reason,
                    "reason_label": reason_label,
                    "field_name": field_name,
                    "label": str(getattr(field, "label", field_name)),
                    "kind": kind,
                    "choices": choices,
                }
            )
    return queue


def current_branch_item(session: dict[str, Any]) -> dict[str, Any] | None:
    queue = session.get("branch_queue") or []
    index = int(session.get("branch_index") or 0)
    if not isinstance(queue, list) or index >= len(queue):
        return None
    item = queue[index]
    return item if isinstance(item, dict) else None


def branch_step4_block(session: dict[str, Any], reason: str) -> dict[str, Any]:
    step4 = step_data(session, "step4")
    block = step4.get(reason)
    if not isinstance(block, dict):
        block = {}
        step4[reason] = block
    return block


def step_data(session: dict[str, Any], step_key: str) -> dict[str, Any]:
    data = session.setdefault("data", {})
    block = data.get(step_key)
    if not isinstance(block, dict):
        block = {}
        data[step_key] = block
    return block


def save_branch_value(session: dict[str, Any], reason: str, field_name: str, value: Any) -> None:
    branch_step4_block(session, reason)[field_name] = value


def init_branch_flow(session: dict[str, Any]) -> str:
    reasons_raw = step_data(session, "step2").get("main_reasons") or []
    reasons = [str(item) for item in reasons_raw] if isinstance(reasons_raw, list) else []
    sex = str(step_data(session, "step1").get("sex") or "female")
    queue = build_branch_queue(reasons, sex)
    session["branch_queue"] = queue
    session["branch_index"] = 0
    if not queue:
        return "s5_files"
    return "s4_branch"


def advance_branch(session: dict[str, Any]) -> str:
    session["branch_index"] = int(session.get("branch_index") or 0) + 1
    queue = session.get("branch_queue") or []
    if session["branch_index"] >= len(queue):
        session["branch_queue"] = []
        session["branch_index"] = 0
        session["multi_field"] = ""
        session["multi_selected"] = []
        return "s5_files"
    return "s4_branch"


def branch_callback_prefix(item: dict[str, Any]) -> str:
    return f"b4:{item['reason']}:{item['field_name']}"


def parse_branch_callback(data: str) -> tuple[str, str, str] | None:
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "b4":
        return None
    return parts[1], parts[2], ":".join(parts[3:])
