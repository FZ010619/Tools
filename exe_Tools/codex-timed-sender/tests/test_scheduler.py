import unittest
from datetime import datetime, timedelta

from timed_sender.models import Draft, ScheduledDelivery
from timed_sender.scheduler import ScheduleState, schedule_state, validate_schedule


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 9, 10, 0, 0)
        self.plan = ScheduledDelivery(None, Draft("继续处理", ()), self.now + timedelta(minutes=10), "enter")

    def test_rejects_past_schedule(self):
        self.assertEqual(validate_schedule(self.now - timedelta(seconds=1), self.now), "发送时间必须晚于当前时间。")

    def test_returns_warning_in_final_five_seconds(self):
        plan = ScheduledDelivery(None, Draft("继续处理", ()), self.now + timedelta(seconds=5), "enter")
        self.assertEqual(schedule_state(plan, self.now), ScheduleState.WARNING)

    def test_returns_due_at_send_time(self):
        plan = ScheduledDelivery(None, Draft("继续处理", ()), self.now, "enter")
        self.assertEqual(schedule_state(plan, self.now), ScheduleState.DUE)

    def test_returns_waiting_before_warning(self):
        self.assertEqual(schedule_state(self.plan, self.now), ScheduleState.WAITING)
