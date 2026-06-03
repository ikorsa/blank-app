from django.test import SimpleTestCase

from telegram_intake.branches import build_branch_queue, init_branch_flow


class BranchQueueTests(SimpleTestCase):
    def test_build_queue_for_diabetes(self) -> None:
        queue = build_branch_queue(["diabetes"], "female")
        self.assertGreater(len(queue), 5)
        self.assertEqual(queue[0]["reason"], "diabetes")
        self.assertIn("kind", queue[0])

    def test_hormones_fields_depend_on_sex(self) -> None:
        female = build_branch_queue(["hormones"], "female")
        male = build_branch_queue(["hormones"], "male")
        female_fields = {item["field_name"] for item in female}
        male_fields = {item["field_name"] for item in male}
        self.assertIn("cycle_regular", female_fields)
        self.assertIn("libido", male_fields)

    def test_init_branch_flow_empty_reasons(self) -> None:
        session = {
            "chat_id": 1,
            "doctor_id": "ivanova",
            "screen": "s3_smoking",
            "data": {"step1": {"sex": "female"}, "step2": {"main_reasons": []}},
        }
        screen = init_branch_flow(session)
        self.assertEqual(screen, "s5_files")
        self.assertEqual(session["branch_queue"], [])

    def test_init_branch_flow_with_reason(self) -> None:
        session = {
            "chat_id": 1,
            "doctor_id": "ivanova",
            "screen": "s3_smoking",
            "data": {"step1": {"sex": "female"}, "step2": {"main_reasons": ["thyroid"]}},
        }
        screen = init_branch_flow(session)
        self.assertEqual(screen, "s4_branch")
        self.assertGreater(len(session["branch_queue"]), 0)
