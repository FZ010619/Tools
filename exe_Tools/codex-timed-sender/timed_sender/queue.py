from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path

from .models import Draft


class QueueItemStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class QueueItem:
    identifier: str
    draft: Draft
    send_key: str
    created_at: datetime
    status: QueueItemStatus = QueueItemStatus.PENDING
    error: str | None = None


@dataclass(frozen=True)
class QueueSettings:
    resume_at: datetime | None = None
    interval_seconds: int = 15
    paused: bool = True
    confirm_first: bool = False
    awaiting_confirmation: bool = False
    next_delivery_at: datetime | None = None


@dataclass(frozen=True)
class QueueState:
    items: list[QueueItem]
    settings: QueueSettings


def default_queue_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return base / "CodexTimedSender" / "queue.json"


class QueueStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_queue_path()

    def load(self) -> QueueState:
        if not self.path.is_file():
            return QueueState([], QueueSettings())
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            settings = self._settings_from_dict(payload.get("settings", {}))
            items = [self._item_from_dict(item) for item in payload.get("items", [])]
            return QueueState(items, settings)
        except (OSError, ValueError, TypeError, KeyError):
            return QueueState([], QueueSettings())

    def save(self, state: QueueState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": [self._item_to_dict(item) for item in state.items],
            "settings": self._settings_to_dict(state.settings),
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def add(self, state: QueueState, item: QueueItem) -> QueueState:
        if any(existing.identifier == item.identifier for existing in state.items):
            raise ValueError("队列项目标识重复。")
        return replace(state, items=[*state.items, item])

    def update(self, state: QueueState, item: QueueItem) -> QueueState:
        if not any(existing.identifier == item.identifier for existing in state.items):
            raise ValueError("未找到要更新的队列项目。")
        return replace(state, items=[item if existing.identifier == item.identifier else existing for existing in state.items])

    def move(self, state: QueueState, identifier: str, offset: int) -> QueueState:
        items = list(state.items)
        index = next((i for i, item in enumerate(items) if item.identifier == identifier), None)
        if index is None:
            raise ValueError("未找到要移动的队列项目。")
        destination = max(0, min(len(items) - 1, index + offset))
        item = items.pop(index)
        items.insert(destination, item)
        return replace(state, items=items)

    def delete(self, state: QueueState, identifier: str) -> QueueState:
        return replace(state, items=[item for item in state.items if item.identifier != identifier])

    @staticmethod
    def _item_to_dict(item: QueueItem) -> dict[str, object]:
        return {
            "identifier": item.identifier,
            "text": item.draft.text,
            "file_paths": [str(path) for path in item.draft.file_paths],
            "image_path": str(item.draft.image_path) if item.draft.image_path else None,
            "send_key": item.send_key,
            "created_at": item.created_at.isoformat(),
            "status": item.status.value,
            "error": item.error,
        }

    @staticmethod
    def _item_from_dict(payload: dict[str, object]) -> QueueItem:
        image = payload.get("image_path")
        return QueueItem(
            str(payload["identifier"]),
            Draft(str(payload.get("text", "")), tuple(Path(path) for path in payload.get("file_paths", [])), Path(image) if image else None),
            str(payload.get("send_key", "enter")),
            datetime.fromisoformat(str(payload["created_at"])),
            QueueItemStatus(str(payload.get("status", QueueItemStatus.PENDING.value))),
            str(payload["error"]) if payload.get("error") else None,
        )

    @staticmethod
    def _settings_to_dict(settings: QueueSettings) -> dict[str, object]:
        return {
            "resume_at": settings.resume_at.isoformat() if settings.resume_at else None,
            "interval_seconds": settings.interval_seconds,
            "paused": settings.paused,
            "confirm_first": settings.confirm_first,
            "awaiting_confirmation": settings.awaiting_confirmation,
            "next_delivery_at": settings.next_delivery_at.isoformat() if settings.next_delivery_at else None,
        }

    @staticmethod
    def _settings_from_dict(payload: dict[str, object]) -> QueueSettings:
        def read_time(name: str) -> datetime | None:
            value = payload.get(name)
            return datetime.fromisoformat(str(value)) if value else None

        return QueueSettings(
            resume_at=read_time("resume_at"),
            interval_seconds=max(1, int(payload.get("interval_seconds", 15))),
            paused=bool(payload.get("paused", True)),
            confirm_first=bool(payload.get("confirm_first", False)),
            awaiting_confirmation=bool(payload.get("awaiting_confirmation", False)),
            next_delivery_at=read_time("next_delivery_at"),
        )
