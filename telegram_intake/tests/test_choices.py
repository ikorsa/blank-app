from unittest.mock import patch

from django.test import SimpleTestCase

from telegram_intake import choices


class WizardChoicesCacheTests(SimpleTestCase):
    def tearDown(self) -> None:
        choices._CACHED_CHOICES = None
        choices._LOAD_ERROR = None

    def test_preload_and_get_use_cache(self) -> None:
        sample = {"sex": [("female", "Женский")]}
        with patch.object(choices, "wizard_choices", return_value=sample) as load:
            self.assertTrue(choices.preload_wizard_choices())
            self.assertEqual(choices.get_wizard_choices(), sample)
            self.assertEqual(choices.get_wizard_choices(), sample)
            load.assert_called_once()

    def test_preload_failure_records_error(self) -> None:
        with patch.object(choices, "wizard_choices", side_effect=RuntimeError("db down")):
            self.assertFalse(choices.preload_wizard_choices())
            self.assertEqual(choices.wizard_choices_error(), "db down")
            with self.assertRaises(RuntimeError):
                choices.get_wizard_choices()
