import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from timed_sender.delivery import DeliveryResult, TargetWindow
from timed_sender.models import Draft
from timed_sender.queue import QueueItem, QueueItemStatus, QueueSettings, QueueState, QueueStore
from timed_sender.queue_runner import QueueRunner


class FakeDelivery:
    def __init__(self, results):
        self.results = list(results)
        self.plans = []

    def deliver(self, plan):
        self.plans.append(plan)
        return self.results.pop(0)


class FailingSentSaveStore(QueueStore):
    def __init__(self, path):
        super().__init__(path)
        self.fail_sent_save = False

    def save(self, state):
        if self.fail_sent_save and any(item.status is QueueItemStatus.SENT for item in state.items):
            raise OSError("disk unavailable")
        super().save(state)


class QueueRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = QueueStore(Path(self.directory.name) / "queue.json")
        self.now = datetime(2026, 10, 10, 10, 0, 0)
        self.target = TargetWindow(1, 2, "Codex")

    def tearDown(self):
        self.directory.cleanup()

    def item(self, identifier):
        return QueueItem(identifier, Draft(identifier, ()), "enter", self.now)

    def runner(self, state, *results):
        self.store.save(state)
        delivery = FakeDelivery(results)
        return QueueRunner(self.store, delivery), delivery

    def test_waits_until_user_supplied_reset_time(self):
        runner, delivery = self.runner(
            QueueState([self.item("one")], QueueSettings(resume_at=self.now + timedelta(minutes=1), paused=False)),
            DeliveryResult(True, "已发送。"),
        )

        result = runner.tick(self.now, self.target)

        self.assertIsNone(result.sent_identifier)
        self.assertEqual(delivery.plans, [])

    def test_sends_pending_items_in_order_with_configured_interval(self):
        runner, delivery = self.runner(
            QueueState(
                [self.item("one"), self.item("two")],
                QueueSettings(resume_at=self.now, interval_seconds=15, paused=False),
            ),
            DeliveryResult(True, "已发送。"),
            DeliveryResult(True, "已发送。"),
        )

        first = runner.tick(self.now, self.target)
        too_early = runner.tick(self.now + timedelta(seconds=14), self.target)
        second = runner.tick(self.now + timedelta(seconds=15), self.target)

        self.assertEqual(first.sent_identifier, "one")
        self.assertIsNone(too_early.sent_identifier)
        self.assertEqual(second.sent_identifier, "two")
        self.assertEqual([plan.draft.text for plan in delivery.plans], ["one", "two"])

    def test_failure_is_retained_and_pauses_queue(self):
        runner, delivery = self.runner(
            QueueState([self.item("one")], QueueSettings(resume_at=self.now, paused=False)),
            DeliveryResult(False, "目标窗口已变化，未发送。"),
        )

        runner.tick(self.now, self.target)
        persisted = self.store.load()

        self.assertEqual(delivery.plans[0].draft.text, "one")
        self.assertEqual(persisted.items[0].status, QueueItemStatus.FAILED)
        self.assertTrue(persisted.settings.paused)

    def test_confirmation_blocks_second_item_until_resumed(self):
        runner, delivery = self.runner(
            QueueState(
                [self.item("one"), self.item("two")],
                QueueSettings(resume_at=self.now, paused=False, confirm_first=True),
            ),
            DeliveryResult(True, "已发送。"),
            DeliveryResult(True, "已发送。"),
        )

        runner.tick(self.now, self.target)
        blocked = runner.tick(self.now + timedelta(seconds=30), self.target)
        runner.resume()
        resumed = runner.tick(self.now + timedelta(seconds=30), self.target)

        self.assertIsNone(blocked.sent_identifier)
        self.assertEqual(resumed.sent_identifier, "two")
        self.assertEqual([plan.draft.text for plan in delivery.plans], ["one", "two"])

    def test_interrupted_in_flight_item_is_paused_for_manual_review_after_restart(self):
        item = QueueItem("one", Draft("one", ()), "enter", self.now, QueueItemStatus.IN_FLIGHT)
        self.store.save(QueueState([item], QueueSettings(resume_at=self.now, paused=False)))

        restarted, delivery = self.runner(self.store.load(), DeliveryResult(True, "已发送。"))
        result = restarted.tick(self.now, self.target)

        self.assertIsNone(result.sent_identifier)
        self.assertEqual(delivery.plans, [])
        self.assertEqual(restarted.state.items[0].status, QueueItemStatus.FAILED)
        self.assertTrue(restarted.state.settings.paused)

    def test_second_runner_reloads_state_and_does_not_duplicate_delivery(self):
        state = QueueState([self.item("one")], QueueSettings(resume_at=self.now, paused=False))
        self.store.save(state)
        first_delivery = FakeDelivery([DeliveryResult(True, "已发送。")])
        second_delivery = FakeDelivery([DeliveryResult(True, "已发送。")])
        first = QueueRunner(self.store, first_delivery)
        second = QueueRunner(self.store, second_delivery)

        first.tick(self.now, self.target)
        second.tick(self.now, self.target)

        self.assertEqual(len(first_delivery.plans), 1)
        self.assertEqual(second_delivery.plans, [])

    def test_save_failure_after_delivery_requires_manual_review_after_restart(self):
        store = FailingSentSaveStore(self.store.path)
        store.save(QueueState([self.item("one")], QueueSettings(resume_at=self.now, paused=False)))
        store.fail_sent_save = True
        runner = QueueRunner(store, FakeDelivery([DeliveryResult(True, "已发送。")]))

        runner.tick(self.now, self.target)
        restarted = QueueRunner(QueueStore(self.store.path), FakeDelivery([DeliveryResult(True, "已发送。")]))
        result = restarted.tick(self.now, self.target)

        self.assertTrue(restarted.state.settings.paused)
        self.assertEqual(restarted.state.items[0].status, QueueItemStatus.FAILED)
        self.assertIsNone(result.sent_identifier)

    def test_configure_preserves_active_interval_and_confirmation_guards(self):
        runner, delivery = self.runner(
            QueueState([self.item("one"), self.item("two")], QueueSettings(resume_at=self.now, paused=False, confirm_first=True)),
            DeliveryResult(True, "已发送。"),
        )
        runner.tick(self.now, self.target)

        runner.configure(QueueSettings(resume_at=self.now, interval_seconds=1, paused=False, confirm_first=False))
        blocked = runner.tick(self.now, self.target)

        self.assertIsNone(blocked.sent_identifier)
        self.assertEqual(len(delivery.plans), 1)
