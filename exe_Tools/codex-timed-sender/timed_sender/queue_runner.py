from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .delivery import DeliveryService, TargetWindow
from .models import ScheduledDelivery
from .queue import QueueItem, QueueItemStatus, QueueSettings, QueueState, QueueStore


@dataclass(frozen=True)
class QueueRunResult:
    sent_identifier: str | None
    message: str


class QueueRunner:
    def __init__(self, store: QueueStore, delivery: DeliveryService) -> None:
        self.store = store
        self.delivery = delivery
        self.state = store.load()

    def replace_settings(self, settings: QueueSettings) -> None:
        self.state = replace(self.state, settings=settings)
        self._save()

    def pause(self) -> None:
        self.replace_settings(replace(self.state.settings, paused=True))

    def resume(self) -> None:
        items = [
            replace(item, status=QueueItemStatus.PENDING, error=None)
            if item.status is QueueItemStatus.FAILED
            else item
            for item in self.state.items
        ]
        settings = replace(self.state.settings, paused=False, awaiting_confirmation=False)
        self.state = QueueState(items, settings)
        self._save()

    def tick(self, now: datetime, target: TargetWindow | None) -> QueueRunResult:
        settings = self.state.settings
        if settings.paused:
            return QueueRunResult(None, "队列已暂停。")
        if settings.resume_at is None:
            return QueueRunResult(None, "请填写额度恢复时间。")
        if now < settings.resume_at:
            return QueueRunResult(None, "等待额度恢复时间。")
        if settings.awaiting_confirmation:
            return QueueRunResult(None, "首条已发送，等待确认后继续。")
        if settings.next_delivery_at is not None and now < settings.next_delivery_at:
            return QueueRunResult(None, "等待下一条发送间隔。")

        item = next((item for item in self.state.items if item.status is QueueItemStatus.PENDING), None)
        if item is None:
            self.replace_settings(replace(settings, paused=True))
            return QueueRunResult(None, "队列已完成。")

        result = self.delivery.deliver(ScheduledDelivery(target, item.draft, now, item.send_key))
        if not result.success:
            self._replace_item(replace(item, status=QueueItemStatus.FAILED, error=result.message))
            self.replace_settings(replace(self.state.settings, paused=True))
            return QueueRunResult(None, result.message)

        first_success = not any(existing.status is QueueItemStatus.SENT for existing in self.state.items)
        self._replace_item(replace(item, status=QueueItemStatus.SENT, error=None))
        settings = replace(
            self.state.settings,
            next_delivery_at=now + timedelta(seconds=self.state.settings.interval_seconds),
            awaiting_confirmation=self.state.settings.confirm_first and first_success,
        )
        self.replace_settings(settings)
        return QueueRunResult(item.identifier, result.message)

    def _replace_item(self, updated: QueueItem) -> None:
        self.state = self.store.update(self.state, updated)
        self._save()

    def _save(self) -> None:
        self.store.save(self.state)
