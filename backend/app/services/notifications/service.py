"""
Sends notifications to all enabled services.

This is the main entry point. When something happens (download finished,
new video found), call one of the convenience methods here.

How it works:
    1. download_completed() calls send(Event.DOWNLOAD_COMPLETED, data)
    2. send() loops through all registered notifiers
    3. For each notifier, checks DB settings to see if it's enabled
    4. Also checks if this specific event is enabled for that notifier
    5. Loads config from DB, merges with any environment variables
    6. Creates notifier instance and calls notify(event, data)
    7. Returns dict of {notifier_id: success} results

Environment variables override database values for sensitive fields:
    NOTIFICATION_{NOTIFIER_ID}_{FIELD_NAME}
    e.g., NOTIFICATION_PLEX_TOKEN, NOTIFICATION_SLACK_WEBHOOK_URL

Uses @classmethod throughout because there's no instance state - it just
reads from DB and dispatches. This matches the pattern in YtDlpService.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.core.logging import get_logger
from app.schemas.notifications import Event
from app.services.notifications.registry import NotifierRegistry

logger = get_logger("notifications")


class NotificationService:
    """Dispatches events to enabled notifiers."""

    @classmethod
    def send(cls, event: Event, data: dict[str, Any]) -> dict[str, bool]:
        """Send event to all enabled notifiers that handle it."""
        from app.extensions import SessionLocal
        from app.models import Settings

        results = {}

        with SessionLocal() as db:
            for info in NotifierRegistry.all():
                nid = info["id"]

                # Check if notifier and event are enabled
                if not Settings.get_bool(db, f"notification_{nid}_enabled", False):
                    continue
                if not Settings.get_bool(
                    db, f"notification_{nid}_event_{event.value}", False
                ):
                    continue

                # Instantiate and dispatch
                try:
                    notifier_cls = NotifierRegistry.get(nid)
                    if not notifier_cls:
                        continue

                    config_json = Settings.get(db, f"notification_{nid}_config", "{}")
                    config = json.loads(config_json) if config_json else {}

                    # Merge with environment variables
                    for field_name in notifier_cls.config_schema:
                        env_name = f"NOTIFICATION_{nid.upper()}_{field_name.upper()}"
                        env_value = os.environ.get(env_name)
                        if env_value:
                            config[field_name] = env_value

                    notifier = notifier_cls(config)
                    results[nid] = notifier.notify(event, data)
                except Exception as e:
                    logger.error("Notifier %s failed: %s", nid, e)
                    results[nid] = False

        return results

    @classmethod
    def download_completed(
        cls, title: str, path: str, list_name: str | None = None
    ) -> None:
        data = {"title": title, "path": path}
        if list_name:
            data["list_name"] = list_name
        cls.send(Event.DOWNLOAD_COMPLETED, data)

    @classmethod
    def video_discovered(cls, title: str, list_name: str, count: int = 1) -> None:
        cls.send(
            Event.VIDEO_DISCOVERED,
            {"title": title, "list_name": list_name, "count": count},
        )

    @classmethod
    def sync_completed(cls, list_name: str, new_videos: int, total: int) -> None:
        cls.send(
            Event.SYNC_COMPLETED,
            {"list_name": list_name, "new_videos": new_videos, "total": total},
        )
