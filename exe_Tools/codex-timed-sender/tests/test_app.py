import unittest
from datetime import datetime, timedelta

from app import build_plan
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
