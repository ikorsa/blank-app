from django.test import SimpleTestCase

from telegram_intake.session import clear_session, load_session, new_session, save_session, step_data
from telegram_intake.wizard import _validate_age, _validate_int, _validate_weight


class TelegramSessionTests(SimpleTestCase):
    def setUp(self) -> None:
        self.chat_id = 999001

    def tearDown(self) -> None:
        clear_session(self.chat_id)

    def test_save_and_load_session(self) -> None:
        session = new_session(self.chat_id, "ivanova")
        step_data(session, "step1")["full_name"] = "Тест"
        save_session(session)
        loaded = load_session(self.chat_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["doctor_id"], "ivanova")
        self.assertEqual(loaded["data"]["step1"]["full_name"], "Тест")


class TelegramValidationTests(SimpleTestCase):
    def test_age_validation(self) -> None:
        self.assertEqual(_validate_age("45"), 45)
        self.assertIsNone(_validate_age("abc"))
        self.assertIsNone(_validate_age("200"))

    def test_height_validation(self) -> None:
        self.assertEqual(_validate_int("170", 50, 250), 170)
        self.assertIsNone(_validate_int("40", 50, 250))

    def test_weight_validation(self) -> None:
        self.assertEqual(_validate_weight("72,5"), 72.5)
        self.assertIsNone(_validate_weight("0"))
