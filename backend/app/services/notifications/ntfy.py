"""ntfy notifier."""

from typing import Any

from app.schemas.notifications import (
    NOTIFY_DISCOVERED,
    NOTIFY_DOWNLOAD,
    NOTIFY_SYNC,
    ConfigField,
)
from app.services.notifications.notifier import HTTPNotifier


class NtfyNotifier(HTTPNotifier):
    """Sends push notifications via ntfy.sh or self-hosted ntfy server."""

    id = "ntfy"
    name = "ntfy"

    config_schema = {
        "server_url": ConfigField(
            type="string",
            label="Server URL",
            placeholder="https://ntfy.sh",
            help="ntfy server URL (default: https://ntfy.sh)",
            required=False,
        ),
        "topic": ConfigField(
            type="string",
            label="Topic",
            placeholder="corvin-downloads",
            help="Topic name to publish to",
        ),
        "access_token": ConfigField(
            type="password",
            label="Access Token",
            placeholder="tk_...",
            required=False,
            help="Access token for authentication (if required)",
        ),
        "priority": ConfigField(
            type="select",
            label="Priority",
            placeholder="default",
            required=False,
            help="Message priority level",
        ),
    }

    supported_events = [NOTIFY_DOWNLOAD, NOTIFY_DISCOVERED, NOTIFY_SYNC]

    # Priority options for the select field
    PRIORITIES = ["min", "low", "default", "high", "urgent"]

    def __init__(self, config: dict[str, Any]) -> None:
        self.server_url = config.get("server_url", "").rstrip("/") or "https://ntfy.sh"
        self.topic = config.get("topic", "")
        self.access_token = config.get("access_token", "")
        self.priority = config.get("priority", "default") or "default"

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="Download Complete",
            message=f"{title}\n{list_name}",
            tags=["tada"],
        )

    def on_video_discovered(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="New Video Discovered",
            message=f"{title}\n{list_name}",
            tags=["loudspeaker"],
        )

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        list_name = data.get("list_name", "Unknown")
        return self._send(
            title="Sync Complete",
            message=list_name,
            tags=["arrows_counterclockwise"],
        )

    def _send(
        self,
        title: str,
        message: str,
        tags: list[str] | None = None,
    ) -> bool:
        if not self.topic:
            return False

        url = f"{self.server_url}/{self.topic}"
        headers: dict[str, str] = {
            "Title": title,
            "Priority": self.priority,
        }

        if tags:
            headers["Tags"] = ",".join(tags)

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return self._safe_request(
            "post", url, data=message.encode("utf-8"), headers=headers
        )

    def test_connection(self) -> tuple[bool, str]:
        if not self.topic:
            return False, "Topic is required"

        try:
            url = f"{self.server_url}/{self.topic}"
            headers: dict[str, str] = {
                "Title": "Test from Corvin",
                "Priority": self.priority,
                "Tags": "white_check_mark",
            }

            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            resp = self._post(
                url,
                data=b"ntfy integration working!",
                headers=headers,
            )
            resp.raise_for_status()
            return True, "Test notification sent"
        except Exception as e:
            return self._handle_error(e)
