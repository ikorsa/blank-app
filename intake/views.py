from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .branch_forms import BranchForm
from .forms import Step1Form, Step2Form, Step3Form, Step5Form, URGENT_SYMPTOM_CHOICES
from .models import Doctor, Draft, Submission, SubmissionFile

SESSION_KEY = "intake_wizard_data"


def _wizard_data(request: HttpRequest) -> dict[str, Any]:
    data = request.session.get(SESSION_KEY)
    if not isinstance(data, dict):
        data = {}
    return data


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _save_wizard_data(request: HttpRequest, data: dict[str, Any]) -> None:
    request.session[SESSION_KEY] = _json_safe(data)
    request.session.modified = True


def _doctor_from_query(request: HttpRequest) -> Doctor | None:
    slug = request.GET.get("doctor", "").strip().lower()
    if not slug:
        return Doctor.objects.filter(is_active=True).order_by("id").first()
    return Doctor.objects.filter(slug=slug, is_active=True).first()


def _load_draft_to_session(request: HttpRequest, doctor: Doctor | None) -> Draft | None:
    draft_raw = request.GET.get("draft", "").strip()
    if not draft_raw:
        return None
    try:
        draft_uuid = UUID(draft_raw)
    except ValueError:
        messages.error(request, "Некорректный идентификатор черновика.")
        return None

    draft = Draft.objects.filter(id=draft_uuid).first()
    if not draft:
        messages.error(request, "Черновик не найден.")
        return None

    if doctor and draft.doctor_id and draft.doctor_id != doctor.id:
        messages.error(request, "Черновик не относится к выбранному врачу.")
        return None

    data = draft.data if isinstance(draft.data, dict) else {}
    _save_wizard_data(request, data)
    return draft


def _save_draft(request: HttpRequest, doctor: Doctor | None) -> Draft:
    data = _wizard_data(request)
    draft_id = request.GET.get("draft", "").strip()
    draft = None
    if draft_id:
        try:
            draft = Draft.objects.filter(id=UUID(draft_id)).first()
        except ValueError:
            draft = None
    if draft:
        draft.data = data
        draft.doctor = doctor
        draft.save(update_fields=["data", "doctor", "updated_at"])
        return draft
    return Draft.objects.create(doctor=doctor, data=data)


def _draft_link(request: HttpRequest, doctor: Doctor | None, draft: Draft) -> str:
    doctor_slug = doctor.slug if doctor else ""
    return f"{reverse('intake:step1')}?doctor={doctor_slug}&draft={draft.id}"


def _query_suffix(doctor: Doctor | None, draft: Draft | None = None) -> str:
    doctor_slug = doctor.slug if doctor else ""
    suffix = f"?doctor={doctor_slug}"
    if draft:
        suffix += f"&draft={draft.id}"
    return suffix


def _step_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _selected_reasons(data: dict[str, Any]) -> list[str]:
    reasons = _step_dict(data, "step2").get("main_reasons")
    return list(reasons) if isinstance(reasons, list) else []


def _patient_sex(data: dict[str, Any]) -> str:
    sex = _step_dict(data, "step1").get("sex")
    return str(sex) if sex in {"female", "male"} else "female"


def _files_step_data(data: dict[str, Any]) -> dict[str, Any]:
    step5 = _step_dict(data, "step5")
    if step5:
        return step5
    step4 = _step_dict(data, "step4")
    if "additional_comment" in step4 or "files" in step4:
        return step4
    return {}


def _branch_step_data(data: dict[str, Any]) -> dict[str, Any]:
    step4 = _step_dict(data, "step4")
    if "additional_comment" in step4:
        return {}
    return step4


def _urgent_symptom_labels(codes: list[str]) -> list[str]:
    labels = dict(URGENT_SYMPTOM_CHOICES)
    return [labels.get(code, code) for code in codes]


def step1(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    wizard_data = _wizard_data(request)
    initial = wizard_data.get("step1", {}) if isinstance(wizard_data.get("step1"), dict) else {}

    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))

        form = Step1Form(request.POST)
        if form.is_valid():
            wizard_data["step1"] = form.cleaned_data
            _save_wizard_data(request, wizard_data)
            return redirect(f"{reverse('intake:step2')}{_query_suffix(doctor, draft)}")
    else:
        form = Step1Form(initial=initial)

    return render(
        request,
        "intake/step1.html",
        {
            "form": form,
            "doctor": doctor,
            "draft": draft,
            "query_suffix": _query_suffix(doctor, draft),
        },
    )


def step2(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    wizard_data = _wizard_data(request)
    step1_data = wizard_data.get("step1")
    if not isinstance(step1_data, dict) or not step1_data:
        messages.warning(request, "Сначала заполните шаг 1.")
        return redirect(f"{reverse('intake:step1')}{_query_suffix(doctor, draft)}")

    initial = wizard_data.get("step2", {}) if isinstance(wizard_data.get("step2"), dict) else {}
    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))

        form = Step2Form(request.POST)
        if form.is_valid():
            wizard_data["step2"] = form.cleaned_data
            _save_wizard_data(request, wizard_data)
            return redirect(f"{reverse('intake:step3')}{_query_suffix(doctor, draft)}")
    else:
        form = Step2Form(initial=initial)

    return render(
        request,
        "intake/step2.html",
        {
            "form": form,
            "doctor": doctor,
            "draft": draft,
            "query_suffix": _query_suffix(doctor, draft),
        },
    )


def step3(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    data = _wizard_data(request)
    if not isinstance(data.get("step2"), dict):
        messages.warning(request, "Сначала заполните шаг 2.")
        return redirect(f"{reverse('intake:step2')}{_query_suffix(doctor, draft)}")
    initial = data.get("step3", {}) if isinstance(data.get("step3"), dict) else {}
    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))
        form = Step3Form(request.POST)
        if form.is_valid():
            data["step3"] = form.cleaned_data
            _save_wizard_data(request, data)
            return redirect(f"{reverse('intake:step4')}{_query_suffix(doctor, draft)}")
    else:
        form = Step3Form(initial=initial)
    return render(
        request,
        "intake/step3.html",
        {"form": form, "doctor": doctor, "draft": draft, "query_suffix": _query_suffix(doctor, draft)},
    )


def step4(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    data = _wizard_data(request)
    if not isinstance(data.get("step3"), dict):
        messages.warning(request, "Сначала заполните шаг 3.")
        return redirect(f"{reverse('intake:step3')}{_query_suffix(doctor, draft)}")

    reasons = _selected_reasons(data)
    if not reasons:
        messages.warning(request, "Выберите причину обращения на шаге 2.")
        return redirect(f"{reverse('intake:step2')}{_query_suffix(doctor, draft)}")

    sex = _patient_sex(data)
    branch_initial = _branch_step_data(data)

    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))

        form = BranchForm(reasons, sex, request.POST, branch_initial=branch_initial)
        if form.is_valid():
            data["step4"] = form.to_branch_dict()
            _save_wizard_data(request, data)
            return redirect(f"{reverse('intake:step5')}{_query_suffix(doctor, draft)}")
    else:
        form = BranchForm(reasons, sex, branch_initial=branch_initial)

    urgent = _step_dict(data, "step1").get("urgent_symptoms") or []
    urgent_labels = _urgent_symptom_labels(list(urgent)) if isinstance(urgent, list) else []

    return render(
        request,
        "intake/step4.html",
        {
            "form": form,
            "sections": form.sections(),
            "doctor": doctor,
            "draft": draft,
            "query_suffix": _query_suffix(doctor, draft),
            "urgent_labels": urgent_labels,
        },
    )


def step5(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    data = _wizard_data(request)
    if not _branch_step_data(data) and not _files_step_data(data):
        if not isinstance(data.get("step3"), dict):
            messages.warning(request, "Сначала заполните шаг 3.")
            return redirect(f"{reverse('intake:step3')}{_query_suffix(doctor, draft)}")
        if not _selected_reasons(data):
            messages.warning(request, "Выберите причину обращения на шаге 2.")
            return redirect(f"{reverse('intake:step2')}{_query_suffix(doctor, draft)}")
        messages.warning(request, "Сначала заполните профильные блоки на шаге 4.")
        return redirect(f"{reverse('intake:step4')}{_query_suffix(doctor, draft)}")

    initial = _files_step_data(data)
    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))
        form = Step5Form(request.POST, request.FILES)
        if form.is_valid():
            data["step5"] = {"additional_comment": form.cleaned_data.get("additional_comment", "")}
            _save_wizard_data(request, data)
            request.session["uploaded_file_names"] = [file.name for file in request.FILES.getlist("files")]
            request.session.modified = True
            return redirect(f"{reverse('intake:summary')}{_query_suffix(doctor, draft)}")
    else:
        form = Step5Form(initial=initial)
    return render(
        request,
        "intake/step5.html",
        {"form": form, "doctor": doctor, "draft": draft, "query_suffix": _query_suffix(doctor, draft)},
    )


def summary(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    data = _wizard_data(request)
    if not _files_step_data(data):
        messages.warning(request, "Сначала заполните шаг 5.")
        return redirect(f"{reverse('intake:step5')}{_query_suffix(doctor, draft)}")

    from .summary import build_submission_summary

    summary_text = build_submission_summary(data)
    urgent = _step_dict(data, "step1").get("urgent_symptoms") or []
    urgent_labels = _urgent_symptom_labels(list(urgent)) if isinstance(urgent, list) else []

    if request.method == "POST":
        submission = Submission.objects.create(doctor=doctor, data=data)
        for uploaded in request.FILES.getlist("files"):
            SubmissionFile.objects.create(submission=submission, file=uploaded)
        request.session.pop(SESSION_KEY, None)
        request.session.pop("uploaded_file_names", None)
        if draft:
            draft.delete()
        messages.success(request, f"Анкета отправлена. ID: {submission.id}")
        return redirect(reverse("intake:step1"))

    return render(
        request,
        "intake/summary.html",
        {
            "data": data,
            "summary_text": summary_text,
            "doctor": doctor,
            "draft": draft,
            "uploaded_names": request.session.get("uploaded_file_names", []),
            "query_suffix": _query_suffix(doctor, draft),
            "urgent_labels": urgent_labels,
        },
    )
