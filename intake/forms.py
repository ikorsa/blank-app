from django import forms

from .models import MAIN_REASONS


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
