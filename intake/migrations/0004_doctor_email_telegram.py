from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0003_doctor_password_submission_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctor",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="doctor",
            name="telegram_chat_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
