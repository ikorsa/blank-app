from __future__ import annotations

from django import forms

from .models import MAIN_REASONS

REASON_LABELS = dict(MAIN_REASONS)

BRANCH_FIELD_LABELS = {
    "diagnosis": "Диагноз",
    "medications": "Препараты",
    "medications_details": "Уточнение по препаратам",
    "insulin": "Инсулин",
    "insulin_types": "Типы инсулина",
    "insulin_regimen": "Режим инсулинотерапии",
    "insulin_daily_units": "Дозы/схема инсулина",
    "first_detected": "Когда выявлено",
    "fasting_glucose": "Сахар натощак",
    "post_meal_glucose": "Сахар после еды",
    "hba1c": "HbA1c",
    "hypoglycemia": "Гипогликемии",
    "complications": "Осложнения/жалобы",
    "dose": "Доза/длительность приема",
    "last_lab_date": "Дата последних анализов",
    "last_tsh_date": "Когда последний раз сдавали ТТГ",
    "last_tsh_value": "ТТГ",
    "free_t4_value": "Т4 свободный",
    "free_t3_value": "Т3 свободный",
    "antibodies": "Антитела",
    "ultrasound": "УЗИ щитовидной железы",
    "ultrasound_findings": "Находки УЗИ",
    "symptoms": "Симптомы",
    "waist_cm": "Окружность талии, см",
    "weight_gain_started": "Когда начался набор веса",
    "weight_gain_amount": "Набор веса за период",
    "max_weight": "Максимальный вес",
    "appetite": "Аппетит",
    "previous_attempts": "Попытки снижения веса",
    "weight_loss_result": "Результат снижения веса",
    "night_eating": "Ночные перекусы",
    "snoring": "Храп/апноэ",
    "sleep_duration": "Сон",
    "physical_activity": "Физическая активность",
    "hypertension": "Повышенное давление",
    "weight_gain_medications": "Лекарства, связанные с набором веса",
    "metabolic_tests": "Сахар/инсулин/HbA1c",
    "libido": "Снижение либидо",
    "fertility": "Вопросы по фертильности или гормонам",
    "hormonal_meds": "Гормональные препараты",
    "cycle_regular": "Регулярность менструального цикла",
    "cycle_length": "Длительность цикла",
    "long_delays": "Задержки более 35 дней",
    "acne": "Акне",
    "hirsutism": "Гирсутизм",
    "hair_loss": "Выпадение волос на голове",
    "pregnancy_history": "Беременности/роды",
    "pregnancy_plans": "Планирование беременности",
    "main_issue": "Что беспокоит больше всего",
    "duration": "Как давно беспокоит",
    "weight_change": "Изменение веса",
    "sleep": "Сон",
    "recent_tests": "Недавние анализы",
    "low_trauma_fractures": "Переломы при небольшой травме",
    "densitometry": "Денситометрия",
    "supplements": "Витамин D / кальций",
    "kidney_stones": "Камни в почках",
    "details": "Описание причины обращения",
    "expectations": "Ожидания от консультации",
}


def format_branch_key(key: str) -> str:
    return BRANCH_FIELD_LABELS.get(key, key.replace("_", " "))


def _choice(label: str, choices: list[tuple[str, str]], required: bool = False) -> forms.ChoiceField:
    return forms.ChoiceField(label=label, choices=choices, required=required)


def _multi(label: str, choices: list[tuple[str, str]], required: bool = False) -> forms.MultipleChoiceField:
    return forms.MultipleChoiceField(
        label=label,
        choices=choices,
        required=required,
        widget=forms.CheckboxSelectMultiple,
    )


def _text(label: str, required: bool = False) -> forms.CharField:
    return forms.CharField(label=label, required=required, max_length=500)


def _textarea(label: str, required: bool = False) -> forms.CharField:
    return forms.CharField(label=label, required=required, widget=forms.Textarea(attrs={"rows": 3}))


def thyroid_fields() -> dict[str, forms.Field]:
    return {
        "diagnosis": _multi(
            "Есть ли установленный диагноз?",
            [
                ("hypo", "Гипотиреоз"),
                ("ait", "АИТ / аутоиммунный тиреоидит"),
                ("nodules", "Узлы щитовидной железы"),
                ("hyper", "Тиреотоксикоз / гипертиреоз"),
                ("surgery", "После операции на щитовидной железе"),
                ("none", "Диагноза нет"),
                ("unknown", "Не знаю"),
            ],
        ),
        "medications": _multi(
            "Принимаете ли препараты для щитовидной железы?",
            [
                ("none", "Не принимаю"),
                ("euthyrox", "Эутирокс"),
                ("lt4", "L-тироксин"),
                ("tyrozol", "Тирозол"),
                ("propicil", "Пропицил"),
                ("iodine", "Йод"),
                ("selenium", "Селен"),
                ("unknown", "Не помню"),
                ("other", "Другое"),
            ],
        ),
        "dose": _text("Укажите дозировку и как давно принимаете"),
        "last_lab_date": _text("Дата последних анализов щитовидной железы"),
        "last_tsh_date": _choice(
            "Когда последний раз сдавали ТТГ?",
            [
                ("", "—"),
                ("lt1m", "Менее 1 месяца назад"),
                ("1_3m", "1-3 месяца назад"),
                ("3_6m", "3-6 месяцев назад"),
                ("gt6m", "Более 6 месяцев назад"),
                ("never", "Не сдавал/не помню"),
            ],
        ),
        "last_tsh_value": _text("Укажите результат ТТГ, если помните"),
        "free_t4_value": _text("Т4 свободный, если помните"),
        "free_t3_value": _text("Т3 свободный, если помните"),
        "antibodies": _multi(
            "Сдавали ли антитела?",
            [("at_tpo", "АТ-ТПО"), ("at_tg", "АТ-ТГ"), ("trab", "Антитела к рецептору ТТГ"), ("never", "Не сдавал/не помню")],
        ),
        "ultrasound": _choice(
            "Есть ли УЗИ щитовидной железы?",
            [("", "—"), ("upload", "Да, могу загрузить"), ("have_not", "Да, но нет с собой"), ("no", "Нет")],
        ),
        "ultrasound_findings": _multi(
            "Что было на УЗИ, если известно?",
            [
                ("nodules", "Узлы"),
                ("cysts", "Кисты"),
                ("enlarged", "Увеличение железы"),
                ("reduced", "Уменьшение железы"),
                ("thyroiditis", "Признаки тиреоидита"),
                ("unknown", "Не знаю"),
            ],
        ),
        "symptoms": _multi(
            "Какие симптомы есть?",
            [
                ("palpitations", "Сердцебиение"),
                ("tremor", "Дрожь в руках"),
                ("sweating", "Потливость"),
                ("irritability", "Раздражительность"),
                ("sleepiness", "Сонливость"),
                ("edema", "Отеки"),
                ("hair_loss", "Выпадение волос"),
                ("dry_skin", "Сухость кожи"),
                ("weight_change", "Изменение веса"),
                ("lump", "Ком в горле"),
                ("none", "Ничего из перечисленного"),
            ],
        ),
    }


def diabetes_fields() -> dict[str, forms.Field]:
    return {
        "diagnosis": _choice(
            "Есть ли диагноз сахарного диабета?",
            [
                ("", "—"),
                ("type1", "Диабет 1 типа"),
                ("type2", "Диабет 2 типа"),
                ("prediabetes", "Предиабет"),
                ("gestational", "Гестационный диабет был раньше"),
                ("high_sugar", "Диагноза нет, но повышен сахар"),
                ("unknown", "Не знаю"),
            ],
        ),
        "first_detected": _text("Когда впервые выявили повышение сахара/диабет?"),
        "medications": _multi(
            "Какие препараты принимаете от сахара?",
            [
                ("none", "Не принимаю"),
                ("metformin", "Метформин"),
                ("sulfonylurea", "Сульфонилмочевина"),
                ("dpp4", "Ингибиторы ДПП-4"),
                ("sglt2", "Ингибиторы SGLT2"),
                ("glp1", "Агонисты ГПП-1"),
                ("tzd", "Тиазолидиндионы"),
                ("acarbose", "Акарбоза"),
                ("insulin_short", "Инсулин короткого действия"),
                ("insulin_long", "Инсулин длительного действия"),
                ("insulin_mix", "Комбинированный инсулин"),
                ("unknown", "Не помню"),
                ("other", "Другое"),
            ],
        ),
        "medications_details": _textarea("Уточните названия, дозировки и режим приема препаратов от сахара"),
        "insulin": _choice("Используете ли инсулин?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "fasting_glucose": _text("Какой сахар обычно натощак?"),
        "post_meal_glucose": _text("Какой сахар обычно после еды?"),
        "hba1c": _text("Последний HbA1c, если знаете"),
        "hypoglycemia": _choice(
            "Бывают ли гипогликемии?",
            [("", "—"), ("no", "Нет"), ("sometimes", "Иногда"), ("often", "Да, часто"), ("not_measured", "Не измеряю")],
        ),
        "complications": _multi(
            "Есть ли осложнения или жалобы?",
            [
                ("vision", "Ухудшение зрения"),
                ("neuropathy", "Онемение/жжение в ногах"),
                ("kidney", "Проблемы с почками"),
                ("wounds", "Раны плохо заживают"),
                ("cardio", "Боли в сердце/сосудах"),
                ("none", "Ничего из перечисленного"),
            ],
        ),
        "insulin_types": _multi(
            "Какой инсулин используете? (если применимо)",
            [
                ("ultra_short", "Ультракороткий"),
                ("short", "Короткий"),
                ("intermediate", "Средней продолжительности"),
                ("long", "Длительный"),
                ("mixed", "Смешанный"),
                ("pump", "Помпа"),
                ("unknown", "Не помню"),
                ("other", "Другое"),
            ],
        ),
        "insulin_regimen": _multi(
            "Какой режим инсулинотерапии? (если применимо)",
            [
                ("once", "1 раз в день"),
                ("twice", "2 раза в день"),
                ("meals", "Перед каждым приемом пищи"),
                ("basal_bolus", "Базис-болюсная схема"),
                ("correction", "Коррекция по сахару"),
                ("pump", "Инсулиновая помпа"),
                ("unknown", "Не знаю"),
                ("other", "Другое"),
            ],
        ),
        "insulin_daily_units": _text("Сколько единиц в сутки или по какой схеме? (если применимо)"),
    }


def weight_fields() -> dict[str, forms.Field]:
    return {
        "waist_cm": _text("Окружность талии, см, если знаете"),
        "weight_gain_started": _choice(
            "Когда начался набор веса?",
            [
                ("", "—"),
                ("childhood", "С детства"),
                ("after18", "После 18 лет"),
                ("pregnancy", "После беременности"),
                ("stress", "После стресса"),
                ("meds", "После начала лекарств"),
                ("recent", "В последние месяцы"),
                ("unknown", "Не знаю"),
            ],
        ),
        "weight_gain_amount": _text("Сколько кг набрали и за какой период?"),
        "max_weight": _text("Максимальный вес в жизни?"),
        "appetite": _choice(
            "Как изменился аппетит?",
            [("", "—"), ("same", "Не изменился"), ("increased", "Повышен"), ("decreased", "Снижен"), ("cravings", "Приступы сильного голода"), ("unknown", "Не знаю")],
        ),
        "previous_attempts": _multi(
            "Были ли попытки снижения веса?",
            [("diet", "Диета"), ("sport", "Спорт"), ("meds", "Лекарства"), ("surgery", "Операция"), ("none", "Нет")],
        ),
        "weight_loss_result": _choice(
            "Вес снижался раньше?",
            [("", "—"), ("returned", "Да, но вернулся"), ("maintained", "Да, удерживаю"), ("no", "Нет"), ("not_tried", "Не пробовал/не пробовала")],
        ),
        "night_eating": _choice("Ночные перекусы или переедание вечером?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("sometimes", "Иногда")]),
        "snoring": _choice("Храп или остановки дыхания во сне?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("unknown", "Не знаю")]),
        "sleep_duration": _choice(
            "Сколько обычно спите?",
            [("", "—"), ("lt5", "Менее 5 часов"), ("5_6", "5-6 часов"), ("7_8", "7-8 часов"), ("gt8", "Более 8 часов"), ("unknown", "Не знаю")],
        ),
        "physical_activity": _choice(
            "Физическая активность",
            [
                ("", "—"),
                ("low", "Низкая"),
                ("walks", "Хожу пешком регулярно"),
                ("1_2", "Тренировки 1-2 раза в неделю"),
                ("3plus", "Тренировки 3+ раза в неделю"),
                ("limited", "Ограничена из-за здоровья"),
            ],
        ),
        "hypertension": _choice("Есть ли повышенное давление?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("unknown", "Не знаю")]),
        "weight_gain_medications": _multi(
            "Были ли лекарства, после которых мог начаться набор веса?",
            [
                ("steroids", "Гормоны/глюкокортикоиды"),
                ("antidepressants", "Антидепрессанты"),
                ("antipsychotics", "Нейролептики"),
                ("insulin", "Инсулин"),
                ("epilepsy", "Препараты от эпилепсии"),
                ("none", "Не было"),
                ("unknown", "Не знаю"),
                ("other", "Другое"),
            ],
        ),
        "metabolic_tests": _choice(
            "Сдавали ли сахар, инсулин, HbA1c?",
            [("", "—"), ("yes", "Да, могу указать/загрузить"), ("no", "Нет"), ("unknown", "Не помню")],
        ),
    }


def hormones_fields_female() -> dict[str, forms.Field]:
    return {
        "cycle_regular": _choice(
            "Регулярный ли менструальный цикл?",
            [("", "—"), ("yes", "Да"), ("no", "Нет"), ("menopause", "Менопауза"), ("pregnant", "Беременность"), ("na", "Не применимо")],
        ),
        "cycle_length": _text("Длительность цикла обычно"),
        "long_delays": _choice("Бывают задержки более 35 дней?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "acne": _choice("Есть ли акне?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "hirsutism": _choice("Есть ли усиленный рост волос на лице/теле?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "hair_loss": _choice("Есть ли выпадение волос на голове?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "pregnancy_history": _textarea("Были ли беременности/роды?"),
        "pregnancy_plans": _choice(
            "Планируете беременность?",
            [("", "—"), ("no", "Нет"), ("yes", "Да"), ("already", "Уже беременна")],
        ),
        "hormonal_meds": _textarea("Принимаете ли гормональные препараты или контрацептивы?"),
    }


def hormones_fields_male() -> dict[str, forms.Field]:
    return {
        "libido": _choice("Есть ли снижение либидо?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("unknown", "Затрудняюсь ответить")]),
        "fertility": _textarea("Есть ли вопросы по фертильности или гормонам?"),
        "hormonal_meds": _textarea("Принимаете ли гормональные препараты?"),
    }


def fatigue_fields() -> dict[str, forms.Field]:
    return {
        "main_issue": _multi(
            "Что беспокоит больше всего?",
            [
                ("weakness", "Слабость"),
                ("sleepiness", "Сонливость"),
                ("hair_loss", "Выпадение волос"),
                ("cold", "Зябкость"),
                ("sweating", "Потливость"),
                ("palpitations", "Сердцебиение"),
                ("edema", "Отечность"),
                ("mood", "Снижение настроения"),
                ("other", "Другое"),
            ],
        ),
        "duration": _text("Как давно это беспокоит?"),
        "weight_change": _choice(
            "Изменился ли вес?",
            [("", "—"), ("same", "Не изменился"), ("gain", "Набрал/набрала"), ("loss", "Похудел/похудела")],
        ),
        "sleep": _choice(
            "Какой сон?",
            [("", "—"), ("normal", "Нормальный"), ("insomnia", "Бессонница"), ("day_sleepiness", "Сонливость днем"), ("awakenings", "Частые пробуждения")],
        ),
        "recent_tests": _choice(
            "Сдавали ли недавно ТТГ, ферритин, витамин D, общий анализ крови?",
            [("", "—"), ("yes", "Да, могу загрузить"), ("no", "Нет"), ("unknown", "Не помню")],
        ),
    }


def bone_fields() -> dict[str, forms.Field]:
    return {
        "diagnosis": _choice("Был ли диагноз остеопороза/остеопении?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("unknown", "Не знаю")]),
        "low_trauma_fractures": _choice("Были ли переломы при небольшой травме?", [("", "—"), ("no", "Нет"), ("yes", "Да")]),
        "densitometry": _choice("Делали ли денситометрию?", [("", "—"), ("yes", "Да, могу загрузить"), ("no", "Нет")]),
        "supplements": _textarea("Принимаете ли витамин D или кальций?"),
        "kidney_stones": _choice("Есть ли камни в почках?", [("", "—"), ("no", "Нет"), ("yes", "Да"), ("unknown", "Не знаю")]),
    }


def other_fields() -> dict[str, forms.Field]:
    return {
        "details": _textarea("Опишите причину обращения своими словами"),
        "expectations": _textarea("Что важно получить от консультации?"),
    }


BRANCH_BUILDERS = {
    "thyroid": lambda _sex: thyroid_fields(),
    "diabetes": lambda _sex: diabetes_fields(),
    "weight": lambda _sex: weight_fields(),
    "hormones": lambda sex: hormones_fields_male() if sex == "male" else hormones_fields_female(),
    "fatigue": lambda _sex: fatigue_fields(),
    "bone": lambda _sex: bone_fields(),
    "other": lambda _sex: other_fields(),
}


def fields_for_reason(reason: str, sex: str) -> dict[str, forms.Field]:
    builder = BRANCH_BUILDERS.get(reason)
    if not builder:
        return {}
    return builder(sex)


def flatten_branch_data(branch_data: dict) -> dict[str, object]:
    flat: dict[str, object] = {}
    if not isinstance(branch_data, dict):
        return flat
    for reason, answers in branch_data.items():
        if not isinstance(answers, dict):
            continue
        for field_name, value in answers.items():
            flat[f"{reason}__{field_name}"] = value
    return flat


def nested_branch_data(cleaned: dict[str, object]) -> dict[str, dict[str, object]]:
    nested: dict[str, dict[str, object]] = {}
    for key, value in cleaned.items():
        if "__" not in key:
            continue
        reason, field_name = key.split("__", 1)
        nested.setdefault(reason, {})[field_name] = value
    return nested
