import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from timed_sender.models import Draft
from timed_sender.queue import QueueItem, QueueItemStatus, QueueSettings, QueueState, QueueStore


class QueueStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = QueueStore(Path(self.directory.name) / "queue.json")
        self.created_at = datetime(2026, 10, 10, 9, 0, 0)

    def tearDown(self):
        self.directory.cleanup()

    def item(self, identifier, text, status=QueueItemStatus.PENDING):
        return QueueItem(identifier, Draft(text, ()), "enter", self.created_at, status)

    def test_persists_items_settings_and_failed_status_after_reload(self):
        state = QueueState(
            [self.item("one", "第一条"), self.item("two", "第二条", QueueItemStatus.FAILED)],
            QueueSettings(resume_at=datetime(2026, 10, 10, 12, 0, 0), interval_seconds=20),
        )

        self.store.save(state)
        loaded = self.store.load()

        self.assertEqual([item.identifier for item in loaded.items], ["one", "two"])
        self.assertEqual(loaded.items[1].status, QueueItemStatus.FAILED)
        self.assertEqual(loaded.settings.resume_at, datetime(2026, 10, 10, 12, 0, 0))
        self.assertEqual(loaded.settings.interval_seconds, 20)

    def test_add_move_update_and_delete_keep_expected_order(self):
        state = QueueState([], QueueSettings())
        state = self.store.add(state, self.item("one", "第一条"))
        state = self.store.add(state, self.item("two", "第二条"))
        state = self.store.move(state, "two", -1)
        state = self.store.update(state, self.item("two", "已修改"))
        state = self.store.delete(state, "one")

        self.assertEqual([item.identifier for item in state.items], ["two"])
        self.assertEqual(state.items[0].draft.text, "已修改")

