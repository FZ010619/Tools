import unittest
from datetime import datetime, timedelta

from app import build_plan, build_queue_item, build_queue_settings
from timed_sender.delivery import TargetWindow


class PlanBuilderTests(unittest.TestCase):
    def test_requires_bound_target(self):
        plan, error = build_plan(None, "继续", (), None, datetime.now() + timedelta(minutes=1), "enter")
        self.assertIsNone(plan)
        self.assertEqual(error, "请先绑定 Codex 窗口。")

    def test_rejects_past_time(self):
        target = TargetWindow(1, 2, "Codex")
        plan, error = build_plan(target, "继续", (), None, datetime.now() - timedelta(seconds=1), "enter")
        self.assertIsNone(plan)
        self.assertEqual(error, "发送时间必须晚于当前时间。")

    def test_builds_valid_plan(self):
        target = TargetWindow(1, 2, "Codex")
        plan, error = build_plan(target, "继续", (), None, datetime.now() + timedelta(minutes=1), "ctrl_enter")
        self.assertIsNone(error)
        self.assertEqual(plan.target, target)
        self.assertEqual(plan.send_key, "ctrl_enter")

    def test_queue_settings_require_bound_target(self):
        settings, error = build_queue_settings(None, "2026-10-10 12:00:00", "15", False)
        self.assertIsNone(settings)
        self.assertEqual(error, "请先绑定 Codex 窗口。")

    def test_queue_settings_reject_invalid_reset_time(self):
        target = TargetWindow(1, 2, "Codex")
        settings, error = build_queue_settings(target, "明天中午", "15", False)
        self.assertIsNone(settings)
        self.assertEqual(error, "额度恢复时间格式不正确。")

    def test_builds_valid_queue_item(self):
        item, error = build_queue_item("继续处理", (), None, "ctrl_enter", "item-1", datetime(2026, 10, 10, 10, 0, 0))
        self.assertIsNone(error)
        self.assertEqual(item.identifier, "item-1")
        self.assertEqual(item.draft.text, "继续处理")
        self.assertEqual(item.send_key, "ctrl_enter")
