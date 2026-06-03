from django.test import SimpleTestCase

from telegram_intake.api import _prepare_payload


class TelegramApiPayloadTests(SimpleTestCase):
    def test_reply_markup_stays_nested_object(self) -> None:
        markup = {"inline_keyboard": [[{"text": "OK", "callback_data": "doc:ivanova"}]]}
        payload = _prepare_payload({"chat_id": 123, "text": "Hi", "reply_markup": markup})
        self.assertEqual(payload["reply_markup"], markup)
        self.assertEqual(payload["chat_id"], 123)

    def test_callback_query_id_is_string(self) -> None:
        payload = _prepare_payload({"callback_query_id": 999888777})
        self.assertEqual(payload["callback_query_id"], 999888777)
