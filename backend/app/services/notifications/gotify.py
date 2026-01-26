"""Gotify notifier."""

from typing import Any

from app.schemas.notifications import (
    NOTIFY_DISCOVERED,
    NOTIFY_DOWNLOAD,
    NOTIFY_SYNC,
    ConfigField,
)
from app.services.notifications.notifier import HTTPNotifier


class GotifyNotifier(HTTPNotifier):
    """Sends push notifications via Gotify server."""

    id = "gotify"
    name = "Gotify"

    config_schema = {
        "server_url": ConfigField(
            type="string",
            label="Server URL",
            placeholder="https://gotify.example.com",
            help="Gotify server URL",
        ),
        "app_token": ConfigField(
            type="password",
            label="App Token",
            placeholder="A...",
            help="Application token from Gotify",
        ),
        "priority": ConfigField(
            type="string",
            label="Priority",
            placeholder="5",
            required=False,
            help="Message priority (0-10, default: 5)",
        ),
    }

    supported_events = [NOTIFY_DOWNLOAD, NOTIFY_DISCOVERED, NOTIFY_SYNC]

    def __init__(self, config: dict[str, Any]) -> None:
        self.server_url = config.get("server_url", "").rstrip("/")
        self.app_token = config.get("app_token", "")
        self.priority = int(config.get("priority") or 5)

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="Download Complete",
            message=f"{title}\n{list_name}",
        )

    def on_video_discovered(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="New Video Discovered",
            message=f"{title}\n{list_name}",
        )

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="Sync Complete",
            message=list_name,
        )

    def _send(self, title: str, message: str) -> bool:
        if not self.server_url or not self.app_token:
            return False

        url = f"{self.server_url}/message"
        return self._safe_request(
            "post",
            url,
            json={
                "title": title,
                "message": message,
                "priority": self.priority,
            },
            headers={"X-Gotify-Key": self.app_token},
        )

    def test_connection(self) -> tuple[bool, str]:
        if not self.server_url:
            return False, "Server URL is required"
        if not self.app_token:
            return False, "App token is required"

        try:
            url = f"{self.server_url}/message"
            resp = self._post(
                url,
                json={
                    "title": "Test from Corvin",
                    "message": "Gotify integration working!",
                    "priority": self.priority,
                },
                headers={"X-Gotify-Key": self.app_token},
            )
            resp.raise_for_status()
            return True, "Test notification sent"
        except Exception as e:
            return self._handle_error(e)
