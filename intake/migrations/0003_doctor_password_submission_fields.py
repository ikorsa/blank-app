from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0002_submission_submissionfile"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctor",
            name="password",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="submission",
            name="appointment_date",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="submission",
            name="doctor_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="submission",
            name="requested_documents",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="submission",
            name="status",
            field=models.CharField(
                choices=[
                    ("submitted", "Новая"),
                    ("in_progress", "В работе"),
                    ("viewed", "Просмотрена"),
                    ("closed", "Закрыта"),
                ],
                default="submitted",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="submission",
            name="viewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
