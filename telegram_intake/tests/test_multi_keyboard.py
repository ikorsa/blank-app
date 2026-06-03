from django.test import SimpleTestCase

from telegram_intake.wizard import _multi_field_for_prefix, _prepare_multi, _resolved_multi_selected, multi_keyboard


class MultiKeyboardTests(SimpleTestCase):
    def test_selected_items_show_checkmark(self) -> None:
        kb = multi_keyboard("s2", [("diabetes", "Диабет"), ("thyroid", "Щитовидка")], ["diabetes"])
        labels = [row[0]["text"] for row in kb["inline_keyboard"][:-1]]
        self.assertTrue(labels[0].startswith("✅"))
        self.assertTrue(labels[1].startswith("☐"))

    def test_done_button_shows_count(self) -> None:
        kb = multi_keyboard("s2", [("a", "A"), ("b", "B")], ["a", "b"])
        done = kb["inline_keyboard"][-1][0]["text"]
        self.assertIn("Готово (2)", done)

    def test_resolved_multi_keeps_in_progress_selection(self) -> None:
        session = {
            "multi_field": "step2.main_reasons",
            "multi_selected": ["diabetes"],
            "data": {"step2": {"main_reasons": []}},
        }
        selected = _resolved_multi_selected(session, "step2.main_reasons", [])
        self.assertEqual(selected, ["diabetes"])

    def test_resolved_multi_loads_stored_when_field_closed(self) -> None:
        session = {"multi_field": "", "multi_selected": [], "data": {}}
        selected = _resolved_multi_selected(session, "step2.main_reasons", ["thyroid"])
        self.assertEqual(selected, ["thyroid"])

    def test_prepare_multi_keeps_toggle_after_field_set(self) -> None:
        session = {
            "screen": "s2_reasons",
            "multi_field": "step2.main_reasons",
            "multi_selected": ["thyroid"],
            "data": {"step2": {"main_reasons": []}},
        }
        selected = _prepare_multi(session, "step2.main_reasons", [])
        self.assertEqual(selected, ["thyroid"])

    def test_multi_field_for_s2_prefix(self) -> None:
        self.assertEqual(_multi_field_for_prefix("s2"), "step2.main_reasons")
