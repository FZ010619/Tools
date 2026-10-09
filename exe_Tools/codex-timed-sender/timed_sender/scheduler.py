from datetime import datetime
from enum import Enum

from .models import ScheduledDelivery


class ScheduleState(str, Enum):
    WAITING = "waiting"
    WARNING = "warning"
    DUE = "due"


def validate_schedule(send_at: datetime, now: datetime) -> str | None:
    return None if send_at > now else "发送时间必须晚于当前时间。"


def schedule_state(plan: ScheduledDelivery, now: datetime) -> ScheduleState:
    seconds_remaining = (plan.send_at - now).total_seconds()
    if seconds_remaining <= 0:
        return ScheduleState.DUE
    if seconds_remaining <= 5:
        return ScheduleState.WARNING
    return ScheduleState.WAITING
