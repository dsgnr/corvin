"""
Notification schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Event(str, Enum):
    """Notification event types."""

    DOWNLOAD_COMPLETED = "download_completed"
    VIDEO_DISCOVERED = "video_discovered"
    SYNC_COMPLETED = "sync_completed"


class EventConfig(BaseModel):
    """Definition for a supported event."""

    event: Event
    label: str
    description: str
    default: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.event.value,
            "label": self.label,
            "description": self.description,
            "default": self.default,
        }


# Pre-defined event configs
SCAN_ON_DOWNLOAD = EventConfig(
    event=Event.DOWNLOAD_COMPLETED,
    label="Scan on Download",
    description="Trigger library scan when a video finishes downloading",
    default=True,
)
SCAN_ON_SYNC = EventConfig(
    event=Event.SYNC_COMPLETED,
    label="Scan on Sync",
    description="Trigger library scan when new videos are discovered",
)
NOTIFY_DOWNLOAD = EventConfig(
    event=Event.DOWNLOAD_COMPLETED,
    label="Download Completed",
    description="Send notification when a video finishes downloading",
    default=True,
)
NOTIFY_DISCOVERED = EventConfig(
    event=Event.VIDEO_DISCOVERED,
    label="Video Discovered",
    description="Send notification when new videos are found",
)
NOTIFY_SYNC = EventConfig(
    event=Event.SYNC_COMPLETED,
    label="Sync Completed",
    description="Send notification when a list sync completes",
)


class ConfigField(BaseModel):
    """Definition for a configuration field."""

    type: str  # "string", "password", "select"
    label: str
    placeholder: str = ""
    required: bool = True
    help: str = ""
    dynamic_options: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "type": self.type,
            "label": self.label,
            "placeholder": self.placeholder,
            "required": self.required,
        }
        if self.help:
            d["help"] = self.help
        if self.dynamic_options:
            d["dynamic_options"] = self.dynamic_options
        return d


class NotifierConfigUpdate(BaseModel):
    """Request body for updating notifier configuration."""

    enabled: bool
    config: dict
    events: dict[str, bool] = {}


class NotifierTestRequest(BaseModel):
    """Request body for testing a notifier connection."""

    config: dict
