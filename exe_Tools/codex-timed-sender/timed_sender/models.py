from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Draft:
    text: str
    file_paths: tuple[Path, ...]
    image_path: Path | None = None


@dataclass(frozen=True)
class ScheduledDelivery:
    target: Any | None
    draft: Draft
    send_at: datetime
    send_key: str
