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


URGENT_SYMPTOM_CHOICES = [
    ("unconscious", "Потеря сознания"),
    ("dyspnea", "Сильная одышка"),
    ("chest_pain", "Боль в груди"),
    ("sugar_gt20", "Сахар выше 20 ммоль/л"),
    ("vomiting_diabetes", "Рвота и выраженная слабость при диабете"),
    ("confusion", "Спутанность сознания"),
]

REPRODUCTIVE_STATUS_CHOICES = [
    ("", "—"),
    ("no", "Нет"),
    ("pregnancy", "Беременность"),
    ("lactation", "Лактация"),
    ("planning", "Планирую беременность"),
    ("menopause", "Менопауза"),
    ("unknown", "Не знаю"),
]


class Step1Form(forms.Form):
    full_name = forms.CharField(
        label="ФИО",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Иванова Мария Петровна", "autocomplete": "name"}),
    )
    age = forms.IntegerField(
        label="Возраст",
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={"placeholder": "45", "inputmode": "numeric"}),
    )
    sex = forms.ChoiceField(
        label="Пол",
        choices=[("female", "Женский"), ("male", "Мужской")],
        widget=forms.RadioSelect,
    )
    phone = forms.CharField(
        label="Телефон для связи",
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "+7 900 000-00-00", "autocomplete": "tel", "inputmode": "tel"}),
    )
    city = forms.CharField(
        label="Город",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Москва", "autocomplete": "address-level2"}),
    )
    height_cm = forms.IntegerField(
        label="Рост, см",
        min_value=1,
        max_value=250,
        widget=forms.NumberInput(attrs={"placeholder": "170", "inputmode": "numeric", "id": "id_height_cm"}),
    )
    weight_kg = forms.DecimalField(
        label="Вес, кг",
        min_value=0.1,
        max_digits=6,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"placeholder": "72.5", "inputmode": "decimal", "step": "0.1", "id": "id_weight_kg"}),
    )
    reproductive_status = forms.ChoiceField(
        label="Беременность / лактация",
        choices=[choice for choice in REPRODUCTIVE_STATUS_CHOICES if choice[0] != ""],
        required=False,
        initial="no",
    )
    urgent_symptoms = forms.MultipleChoiceField(
        label="Отметьте, если есть сейчас",
        choices=URGENT_SYMPTOM_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


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
    chronic_conditions = forms.MultipleChoiceField(
        label="Какие хронические заболевания есть?",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[
            ("none", "Нет хронических заболеваний"),
            ("hypertension", "Артериальная гипертония"),
            ("diabetes", "Сахарный диабет"),
            ("thyroid", "Заболевания щитовидной железы"),
            ("heart", "Ишемическая болезнь сердца / стенокардия"),
            ("arrhythmia", "Аритмия"),
            ("stroke", "Инфаркт или инсульт в прошлом"),
            ("kidney", "Хронические заболевания почек"),
            ("liver", "Хронические заболевания печени"),
            ("gastro", "Заболевания желудка/кишечника"),
            ("lung", "Бронхиальная астма / ХОБЛ"),
            ("autoimmune", "Аутоиммунные заболевания"),
            ("oncology", "Онкологические заболевания"),
            ("osteoporosis", "Остеопороз"),
            ("mental", "Депрессия / тревожное расстройство"),
            ("unknown", "Не знаю"),
            ("other", "Другое"),
        ],
    )
    chronic_conditions_other = forms.CharField(
        label="Уточните хронические заболевания (если выбрали «Другое»)",
        required=False,
    )
    surgeries = forms.CharField(label="Были ли операции?", required=False, widget=forms.Textarea)
    medications = forms.MultipleChoiceField(
        label="Какие лекарства принимаете постоянно?",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[
            ("none", "Не принимаю постоянно"),
            ("pressure", "Препараты от давления"),
            ("sugar", "Препараты от сахара"),
            ("insulin", "Инсулин"),
            ("lt4", "L-тироксин / Эутирокс"),
            ("thyro", "Тирозол / пропицил"),
            ("statin", "Статины / препараты холестерина"),
            ("blood", "Антикоагулянты / антиагреганты"),
            ("diuretic", "Мочегонные"),
            ("hormonal", "Гормональные препараты / контрацептивы"),
            ("antidepressant", "Антидепрессанты / противотревожные"),
            ("steroid", "Глюкокортикоиды"),
            ("vitd", "Витамин D / кальций"),
            ("supplements", "БАДы"),
            ("unknown", "Не помню"),
            ("other", "Другое"),
        ],
    )
    medications_details = forms.CharField(
        label="Уточните названия, дозировки и режим приема",
        required=False,
        widget=forms.Textarea,
    )
    allergy_status = forms.ChoiceField(
        label="Есть ли аллергии на лекарства?",
        required=False,
        choices=[("no", "Нет"), ("yes", "Да"), ("unknown", "Не знаю")],
    )
    allergies_details = forms.CharField(
        label="Если «Да», укажите на какие лекарства и какая реакция",
        required=False,
        widget=forms.Textarea,
    )
    family_history = forms.MultipleChoiceField(
        label="Есть ли у родственников эндокринные заболевания?",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[
            ("diabetes", "Диабет"),
            ("thyroid", "Болезни щитовидной железы"),
            ("obesity", "Ожирение"),
            ("osteoporosis", "Остеопороз"),
            ("unknown", "Не знаю"),
            ("none", "Нет"),
        ],
    )
    blood_pressure = forms.CharField(label="Ваше обычное артериальное давление?", required=False)
    smoking = forms.ChoiceField(
        label="Курите?",
        required=False,
        choices=[("no", "Нет"), ("yes", "Да"), ("quit", "Бросил/бросила")],
    )


class Step5Form(forms.Form):
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
        fields = ["slug", "name", "specialty", "email", "telegram_chat_id", "password", "is_active"]
        labels = {
            "slug": "Код врача (slug)",
            "name": "ФИО",
            "specialty": "Специальность",
            "email": "Email",
            "telegram_chat_id": "Telegram chat_id",
            "password": "Пароль кабинета",
            "is_active": "Активен",
        }
