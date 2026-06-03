from django.test import SimpleTestCase

from telegram_intake.picker import doctor_short_label, doctors_picker_keyboard


class DoctorPickerTests(SimpleTestCase):
    def test_keyboard_buttons_for_doctors(self) -> None:
        doctors = [
            {"id": "ivanova", "name": "Иванова А.С.", "specialty": "Эндокринолог"},
            {"id": "petrov", "name": "Петров И.П.", "specialty": "Эндокринолог"},
        ]
        kb = doctors_picker_keyboard(doctors)
        self.assertEqual(len(kb["inline_keyboard"]), 2)
        self.assertEqual(kb["inline_keyboard"][0][0]["callback_data"], "doc:ivanova")
        self.assertIn("Иванова", kb["inline_keyboard"][0][0]["text"])

    def test_short_label(self) -> None:
        label = doctor_short_label({"id": "x", "name": "Тест", "specialty": "Эндокринолог"})
        self.assertIn("Тест", label)
