from django.test import SimpleTestCase

from telegram_intake.api import _prepare_payload


class TelegramApiPayloadTests(SimpleTestCase):
    def test_reply_markup_is_json_string(self) -> None:
        payload = _prepare_payload(
            {
                "chat_id": 123,
                "text": "Hi",
                "reply_markup": {"inline_keyboard": [[{"text": "OK", "callback_data": "doc:ivanova"}]]},
            }
        )
        self.assertIsInstance(payload["reply_markup"], str)
        self.assertIn("inline_keyboard", payload["reply_markup"])
        self.assertEqual(payload["chat_id"], 123)
