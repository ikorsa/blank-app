from unittest.mock import patch

from django.test import SimpleTestCase

from telegram_intake import choices
from telegram_intake.wizard import _callback_matches_multi_screen


class WizardChoicesCacheTests(SimpleTestCase):
    def tearDown(self) -> None:
        choices._CACHED_CHOICES = None
        choices._LOAD_ERROR = None

    def test_preload_and_get_use_cache(self) -> None:
        sample = {"sex": [("female", "Женский")]}
        with patch.object(choices, "wizard_choices", return_value=sample) as load:
            self.assertTrue(choices.preload_wizard_choices())
            self.assertEqual(choices.get_wizard_choices(), sample)
            load.assert_called_once()


class MultiScreenCallbackTests(SimpleTestCase):
    def test_accepts_matching_chronic_toggle(self) -> None:
        session = {"screen": "s3_chronic"}
        self.assertTrue(_callback_matches_multi_screen(session, "s3_chron:t:diabetes"))

    def test_rejects_stale_reasons_on_chronic_step(self) -> None:
        session = {"screen": "s3_chronic"}
        self.assertFalse(_callback_matches_multi_screen(session, "s2:done"))
