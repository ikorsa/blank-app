import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from telegram_intake.session import ensure_session_storage, session_dir


class SessionStorageTests(SimpleTestCase):
    def test_ensure_session_storage_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ANAMNES_DATA_DIR"] = tmp
            path = ensure_session_storage()
            self.assertTrue(path.exists())
            self.assertEqual(path, session_dir())
