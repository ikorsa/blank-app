import uuid

from django.db import migrations, models
import django.db.models.deletion
import intake.models


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Submission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "doctor",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="intake.doctor"),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SubmissionFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to=intake.models.submission_upload_path)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "submission",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="files", to="intake.submission"),
                ),
            ],
        ),
    ]
