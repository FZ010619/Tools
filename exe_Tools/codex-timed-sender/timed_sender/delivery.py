from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Protocol

from .content import format_message
from .models import ScheduledDelivery


@dataclass(frozen=True)
class TargetWindow:
    handle: int
    process_id: int
    title: str


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    message: str


class WindowsAdapter(Protocol):
    def target_is_valid(self, target: TargetWindow) -> bool: ...
    def activate(self, target: TargetWindow) -> bool: ...
    def paste_image(self, image_path: Path) -> bool: ...
    def paste_text(self, text: str) -> bool: ...
    def send_key(self, key: str) -> None: ...


class DeliveryService:
    def __init__(self, adapter: WindowsAdapter) -> None:
        self.adapter = adapter

    def deliver(self, plan: ScheduledDelivery) -> DeliveryResult:
        target = plan.target
        if not isinstance(target, TargetWindow) or not self.adapter.target_is_valid(target):
            return DeliveryResult(False, "目标窗口已变化，未发送。")
        if not self.adapter.activate(target):
            return DeliveryResult(False, "无法激活目标窗口，未发送。")
        if plan.draft.image_path is not None:
            if not self.adapter.paste_image(plan.draft.image_path):
                return DeliveryResult(False, "图片粘贴失败，未发送。")
            sleep(0.3)
        message = format_message(plan.draft)
        if message and not self.adapter.paste_text(message):
            return DeliveryResult(False, "文本粘贴失败，未发送。")
        self.adapter.send_key(plan.send_key)
        return DeliveryResult(True, "已发送。")
