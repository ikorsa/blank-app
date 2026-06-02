from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import Step1Form, Step2Form, Step3Form, Step4Form
from .models import Doctor, Draft, Submission, SubmissionFile

SESSION_KEY = "intake_wizard_data"


def _wizard_data(request: HttpRequest) -> dict[str, Any]:
    data = request.session.get(SESSION_KEY)
    if not isinstance(data, dict):
        data = {}
    return data


def _save_wizard_data(request: HttpRequest, data: dict[str, Any]) -> None:
    request.session[SESSION_KEY] = data
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
    initial = data.get("step4", {}) if isinstance(data.get("step4"), dict) else {}
    if request.method == "POST":
        if request.POST.get("save_draft") == "1":
            draft = _save_draft(request, doctor)
            messages.success(request, f"Черновик сохранён: {_draft_link(request, doctor, draft)}")
            return redirect(_draft_link(request, doctor, draft))
        form = Step4Form(request.POST, request.FILES)
        if form.is_valid():
            data["step4"] = {"additional_comment": form.cleaned_data.get("additional_comment", "")}
            _save_wizard_data(request, data)
            request.session["uploaded_file_names"] = [file.name for file in request.FILES.getlist("files")]
            request.session.modified = True
            return redirect(f"{reverse('intake:summary')}{_query_suffix(doctor, draft)}")
    else:
        form = Step4Form(initial=initial)
    return render(
        request,
        "intake/step4.html",
        {"form": form, "doctor": doctor, "draft": draft, "query_suffix": _query_suffix(doctor, draft)},
    )


def summary(request: HttpRequest) -> HttpResponse:
    doctor = _doctor_from_query(request)
    draft = _load_draft_to_session(request, doctor)
    data = _wizard_data(request)
    if not isinstance(data.get("step4"), dict):
        messages.warning(request, "Сначала заполните шаг 4.")
        return redirect(f"{reverse('intake:step4')}{_query_suffix(doctor, draft)}")

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
            "doctor": doctor,
            "draft": draft,
            "uploaded_names": request.session.get("uploaded_file_names", []),
            "query_suffix": _query_suffix(doctor, draft),
        },
    )
