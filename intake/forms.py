from django import forms

from .models import Doctor, MAIN_REASONS, Submission


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        if not data:
            return []
        return [single_file_clean(data, initial)]


class Step1Form(forms.Form):
    full_name = forms.CharField(label="ФИО", max_length=255)
    age = forms.IntegerField(label="Возраст", min_value=1, max_value=120)
    sex = forms.ChoiceField(label="Пол", choices=[("female", "Женский"), ("male", "Мужской")])
    phone = forms.CharField(label="Телефон", max_length=50)
    city = forms.CharField(label="Город", max_length=120)
    height_cm = forms.IntegerField(label="Рост, см", min_value=1, max_value=250)
    weight_kg = forms.DecimalField(label="Вес, кг", min_value=0.1, max_digits=6, decimal_places=1)


class Step2Form(forms.Form):
    main_reasons = forms.MultipleChoiceField(
        label="Причина обращения",
        choices=MAIN_REASONS,
        widget=forms.CheckboxSelectMultiple,
    )


class Step3Form(forms.Form):
    complaints = forms.CharField(label="Какие жалобы беспокоят сейчас?", widget=forms.Textarea, required=False)
    complaints_started = forms.ChoiceField(
        label="Когда появились жалобы?",
        choices=[
            ("week", "Менее недели назад"),
            ("month", "1-4 недели назад"),
            ("half_year", "1-6 месяцев назад"),
            ("long", "Более 6 месяцев назад"),
            ("unknown", "Затрудняюсь ответить"),
        ],
        required=False,
    )
    medications = forms.CharField(label="Какие лекарства принимаете постоянно?", widget=forms.Textarea, required=False)


class Step4Form(forms.Form):
    additional_comment = forms.CharField(label="Комментарий для врача", widget=forms.Textarea, required=False)
    files = MultipleFileField(label="Файлы (PDF/JPG/PNG)", required=False)


class DoctorLoginForm(forms.Form):
    login = forms.CharField(label="Логин врача или admin", max_length=64)
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)


class SubmissionDoctorForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["status", "appointment_date", "requested_documents", "doctor_note"]
        widgets = {
            "doctor_note": forms.Textarea(attrs={"rows": 4}),
            "requested_documents": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "status": "Статус анкеты",
            "appointment_date": "Дата приёма",
            "requested_documents": "Что попросить донести",
            "doctor_note": "Комментарий врача",
        }


class DoctorAdminForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ["slug", "name", "specialty", "password", "is_active"]
        labels = {
            "slug": "Код врача (slug)",
            "name": "ФИО",
            "specialty": "Специальность",
            "password": "Пароль кабинета",
            "is_active": "Активен",
        }
