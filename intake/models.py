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
