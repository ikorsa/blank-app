from django.urls import path

from . import doctor_views, views

app_name = "intake"

urlpatterns = [
    path("", views.step1, name="step1"),
    path("step-2/", views.step2, name="step2"),
    path("step-3/", views.step3, name="step3"),
    path("step-4/", views.step4, name="step4"),
    path("summary/", views.summary, name="summary"),
    path("doctor/login/", doctor_views.doctor_login, name="doctor_login"),
    path("doctor/logout/", doctor_views.doctor_logout, name="doctor_logout"),
    path("doctor/", doctor_views.doctor_dashboard, name="doctor_dashboard"),
    path("doctor/submission/<uuid:submission_id>/", doctor_views.doctor_submission_detail, name="doctor_submission_detail"),
    path(
        "doctor/submission/<uuid:submission_id>/summary.txt",
        doctor_views.doctor_submission_summary_txt,
        name="doctor_submission_summary_txt",
    ),
]
