import uuid

from django.db import models


MAIN_REASONS = [
    ("thyroid", "Щитовидная железа"),
    ("diabetes", "Сахарный диабет / высокий сахар"),
    ("weight", "Лишний вес / ожирение"),
    ("hormones", "Нарушение цикла / гормоны / бесплодие"),
    ("fatigue", "Усталость / слабость / выпадение волос"),
    ("bone", "Остеопороз / витамин D / кальций"),
    ("other", "Другое"),
]


class Doctor(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    specialty = models.CharField(max_length=255, default="Эндокринолог")
    password = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.specialty})"


class Draft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Draft {self.id}"


SUBMISSION_STATUSES = [
    ("submitted", "Новая"),
    ("in_progress", "В работе"),
    ("viewed", "Просмотрена"),
    ("closed", "Закрыта"),
]


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUSES, default="submitted")
    doctor_note = models.TextField(blank=True, default="")
    requested_documents = models.TextField(blank=True, default="")
    appointment_date = models.CharField(max_length=120, blank=True, default="")
    viewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Submission {self.id}"


def submission_upload_path(instance: "SubmissionFile", filename: str) -> str:
    return f"submissions/{instance.submission_id}/{filename}"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=submission_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
