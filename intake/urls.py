from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.step1, name="step1"),
    path("step-2/", views.step2, name="step2"),
    path("step-3/", views.step3, name="step3"),
    path("step-4/", views.step4, name="step4"),
    path("summary/", views.summary, name="summary"),
]
