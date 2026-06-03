from django.test import SimpleTestCase

from telegram_intake.api import (
    POLL_HTTP_TIMEOUT,
    POLL_TIMEOUT,
    REQUEST_TIMEOUT,
    TelegramNetworkError,
    _prepare_payload,
    api_request,
)


class TelegramApiPayloadTests(SimpleTestCase):
    def test_reply_markup_stays_nested_object(self) -> None:
        markup = {"inline_keyboard": [[{"text": "OK", "callback_data": "doc:ivanova"}]]}
        payload = _prepare_payload({"chat_id": 123, "text": "Hi", "reply_markup": markup})
        self.assertEqual(payload["reply_markup"], markup)
        self.assertEqual(payload["chat_id"], 123)

    def test_poll_http_timeout_covers_long_poll(self) -> None:
        self.assertGreater(POLL_HTTP_TIMEOUT, POLL_TIMEOUT)
        self.assertGreaterEqual(REQUEST_TIMEOUT, 10)


class TelegramNetworkErrorTests(SimpleTestCase):
    def test_url_error_wrapped(self) -> None:
        from unittest.mock import patch
        from urllib.error import URLError

        with patch("telegram_intake.api.BOT_TOKEN", "test-token"):
            with patch("telegram_intake.api.urlopen", side_effect=URLError("timed out")):
                with self.assertRaises(TelegramNetworkError) as ctx:
                    api_request("getMe")
        self.assertIn("network error", str(ctx.exception).lower())
