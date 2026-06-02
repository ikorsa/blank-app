from __future__ import annotations

from functools import wraps
from typing import Callable

from django.conf import settings
import json

from django.contrib import messages
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import DoctorLoginForm, SubmissionDoctorForm
from .models import Doctor, Submission
from .summary import build_submission_summary, patient_name, reason_labels

SESSION_ROLE = "dc_role"
SESSION_SLUG = "dc_slug"
SESSION_NAME = "dc_name"


def _auth_context(request: HttpRequest) -> dict[str, str]:
    return {
        "role": request.session.get(SESSION_ROLE, ""),
        "slug": request.session.get(SESSION_SLUG, ""),
        "name": request.session.get(SESSION_NAME, ""),
    }


def doctor_login_required(view_func: Callable) -> Callable:
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.session.get(SESSION_ROLE):
            return redirect("intake:doctor_login")
        return view_func(request, *args, **kwargs)

    return wrapper


def _submissions_for_user(request: HttpRequest) -> QuerySet[Submission]:
    auth = _auth_context(request)
    qs = Submission.objects.select_related("doctor").prefetch_related("files")
    if auth["role"] == "admin":
        return qs
    if auth["role"] == "doctor" and auth["slug"]:
        return qs.filter(doctor__slug=auth["slug"])
    return qs.none()


def doctor_login(request: HttpRequest) -> HttpResponse:
    if request.session.get(SESSION_ROLE):
        return redirect("intake:doctor_dashboard")

    if request.method == "POST":
        form = DoctorLoginForm(request.POST)
        if form.is_valid():
            login = form.cleaned_data["login"].strip().lower()
            password = form.cleaned_data["password"]

            if login == "admin" and password == settings.ANAMNES_ADMIN_PASSWORD:
                request.session[SESSION_ROLE] = "admin"
                request.session[SESSION_SLUG] = ""
                request.session[SESSION_NAME] = "Администратор"
                request.session.modified = True
                return redirect("intake:doctor_dashboard")

            doctor = Doctor.objects.filter(slug=login, is_active=True).first()
            if doctor and doctor.password and doctor.password == password:
                request.session[SESSION_ROLE] = "doctor"
                request.session[SESSION_SLUG] = doctor.slug
                request.session[SESSION_NAME] = doctor.name
                request.session.modified = True
                return redirect("intake:doctor_dashboard")

            messages.error(request, "Неверный логин или пароль.")
    else:
        form = DoctorLoginForm()

    return render(request, "doctor/login.html", {"form": form})


def doctor_logout(request: HttpRequest) -> HttpResponse:
    for key in (SESSION_ROLE, SESSION_SLUG, SESSION_NAME):
        request.session.pop(key, None)
    request.session.modified = True
    return redirect("intake:doctor_login")


@doctor_login_required
def doctor_dashboard(request: HttpRequest) -> HttpResponse:
    auth = _auth_context(request)
    qs = _submissions_for_user(request)

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    if search:
        qs = qs.filter(
            Q(data__step1__full_name__icontains=search)
            | Q(data__step1__phone__icontains=search)
            | Q(id__icontains=search)
        )
    if status != "all":
        qs = qs.filter(status=status)

    submissions = list(qs.order_by("-created_at")[:200])
    for item in submissions:
        item.patient_label = patient_name(item.data if isinstance(item.data, dict) else {})
        item.reason_label = reason_labels(item.data if isinstance(item.data, dict) else {})

    return render(
        request,
        "doctor/dashboard.html",
        {
            "auth": auth,
            "submissions": submissions,
            "search": search,
            "status": status,
            "status_choices": Submission._meta.get_field("status").choices,
            "total": len(submissions),
        },
    )


@doctor_login_required
def doctor_submission_detail(request: HttpRequest, submission_id) -> HttpResponse:
    auth = _auth_context(request)
    submission = get_object_or_404(_submissions_for_user(request), id=submission_id)

    if request.method == "POST":
        form = SubmissionDoctorForm(request.POST, instance=submission)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.status in {"viewed", "in_progress", "closed"} and not updated.viewed_at:
                updated.viewed_at = timezone.now()
            updated.save()
            messages.success(request, "Служебные поля сохранены.")
            return redirect("intake:doctor_submission_detail", submission_id=submission.id)
    else:
        form = SubmissionDoctorForm(instance=submission)

    data = submission.data if isinstance(submission.data, dict) else {}
    return render(
        request,
        "doctor/detail.html",
        {
            "auth": auth,
            "submission": submission,
            "form": form,
            "summary_text": build_submission_summary(submission),
            "data_json": json.dumps(data, ensure_ascii=False, indent=2),
        },
    )


@doctor_login_required
def doctor_submission_summary_txt(request: HttpRequest, submission_id) -> HttpResponse:
    submission = get_object_or_404(_submissions_for_user(request), id=submission_id)
    content = build_submission_summary(submission)
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="summary_{submission.id}.txt"'
    return response
