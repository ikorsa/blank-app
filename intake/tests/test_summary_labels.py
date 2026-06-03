from django.test import SimpleTestCase

from intake.choice_labels import format_branch_value, format_step3_value
from intake.summary import build_submission_summary


class ChoiceLabelTests(SimpleTestCase):
    def test_step3_multiselect_labels(self):
        text = format_step3_value("chronic_conditions", ["diabetes", "thyroid"])
        self.assertIn("Сахарный диабет", text)
        self.assertIn("Заболевания щитовидной железы", text)
        self.assertNotIn("diabetes", text)

    def test_step3_choice_label(self):
        self.assertEqual(format_step3_value("smoking", "quit"), "Бросил/бросила")

    def test_branch_multiselect_labels(self):
        text = format_branch_value("thyroid", "symptoms", ["palpitations", "edema"])
        self.assertIn("Сердцебиение", text)
        self.assertIn("Отеки", text)

    def test_branch_choice_label(self):
        self.assertEqual(format_branch_value("diabetes", "diagnosis", "type2"), "Диабет 2 типа")


class SummaryTextTests(SimpleTestCase):
    def test_summary_uses_russian_labels(self):
        data = {
            "step1": {"full_name": "Тест", "age": 40, "sex": "female", "height_cm": 170, "weight_kg": 70},
            "step2": {"main_reasons": ["diabetes"]},
            "step3": {
                "complaints": "Жажда",
                "complaints_started": "month",
                "chronic_conditions": ["diabetes"],
                "medications": ["metformin"],
                "allergy_status": "no",
                "family_history": ["thyroid"],
                "smoking": "no",
            },
            "step4": {
                "diabetes": {
                    "diagnosis": "type2",
                    "hypoglycemia": "sometimes",
                    "medications": ["metformin", "insulin_long"],
                }
            },
            "step5": {},
        }
        summary = build_submission_summary(data)
        self.assertIn("1-4 недели назад", summary)
        self.assertIn("Сахарный диабет", summary)
        self.assertIn("Метформин", summary)
        self.assertIn("Диабет 2 типа", summary)
        self.assertIn("Иногда", summary)
        self.assertNotIn("type2", summary)
        self.assertNotIn("sometimes", summary)
