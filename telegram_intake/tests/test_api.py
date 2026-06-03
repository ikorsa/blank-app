from unittest.mock import patch

from django.test import SimpleTestCase

from telegram_intake.api import _prepare_payload, try_edit_message


class TelegramApiPayloadTests(SimpleTestCase):
    def test_reply_markup_stays_nested_object(self) -> None:
        markup = {"inline_keyboard": [[{"text": "OK", "callback_data": "doc:ivanova"}]]}
        payload = _prepare_payload({"chat_id": 123, "text": "Hi", "reply_markup": markup})
        self.assertEqual(payload["reply_markup"], markup)
        self.assertEqual(payload["chat_id"], 123)


class TryEditMessageTests(SimpleTestCase):
    def test_not_modified_is_success(self) -> None:
        with patch("telegram_intake.api.edit_message", side_effect=RuntimeError("HTTP 400: message is not modified")):
            self.assertTrue(try_edit_message(1, 2, "text", None))

    def test_real_error_returns_false(self) -> None:
        with patch("telegram_intake.api.edit_message", side_effect=RuntimeError("HTTP 400: bad markup")):
            self.assertFalse(try_edit_message(1, 2, "text", None))
