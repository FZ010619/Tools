import unittest
from datetime import datetime, timedelta
from pathlib import Path

from timed_sender.delivery import DeliveryService, TargetWindow
from timed_sender.models import Draft, ScheduledDelivery


class FakeAdapter:
    def __init__(self, valid=True, focused=True, image_ok=True, text_ok=True):
        self.valid, self.focused, self.image_ok, self.text_ok = valid, focused, image_ok, text_ok
        self.calls = []

    def target_is_valid(self, target): self.calls.append("verify"); return self.valid
    def activate(self, target): self.calls.append("focus"); return self.focused
    def paste_image(self, image_path): self.calls.append("image"); return self.image_ok
    def paste_text(self, text): self.calls.append("text"); return self.text_ok
    def send_key(self, key): self.calls.append(f"send:{key}")


class DeliveryTests(unittest.TestCase):
    def make_plan(self, image_path=None):
        return ScheduledDelivery(TargetWindow(101, 202, "Codex — Test"), Draft("继续", (Path(r"D:\work\file.txt"),), image_path), datetime.now() + timedelta(minutes=1), "ctrl_enter")

    def test_invalid_target_never_pastes_or_sends(self):
        adapter = FakeAdapter(valid=False)
        self.assertFalse(DeliveryService(adapter).deliver(self.make_plan()).success)
        self.assertEqual(adapter.calls, ["verify"])

    def test_failed_focus_never_pastes_or_sends(self):
        adapter = FakeAdapter(focused=False)
        self.assertFalse(DeliveryService(adapter).deliver(self.make_plan()).success)
        self.assertEqual(adapter.calls, ["verify", "focus"])

    def test_successful_text_delivery_verifies_focuses_pastes_and_sends(self):
        adapter = FakeAdapter()
        self.assertTrue(DeliveryService(adapter).deliver(self.make_plan()).success)
        self.assertEqual(adapter.calls, ["verify", "focus", "text", "send:ctrl_enter"])

    def test_failed_image_stops_before_text_and_send(self):
        adapter = FakeAdapter(image_ok=False)
        self.assertFalse(DeliveryService(adapter).deliver(self.make_plan(Path(r"D:\screen.png"))).success)
        self.assertEqual(adapter.calls, ["verify", "focus", "image"])
