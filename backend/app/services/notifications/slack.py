"""Slack webhook notifier."""

from typing import Any

from app.schemas.notifications import (
    NOTIFY_DISCOVERED,
    NOTIFY_DOWNLOAD,
    NOTIFY_SYNC,
    ConfigField,
)
from app.services.notifications.notifier import HTTPNotifier


class SlackNotifier(HTTPNotifier):
    """Sends notifications to Slack via incoming webhooks."""

    id = "slack"
    name = "Slack"

    config_schema = {
        "webhook_url": ConfigField(
            type="password",
            label="Webhook URL",
            placeholder="https://hooks.slack.com/services/...",
            help="Create at api.slack.com/apps",
        ),
        "channel": ConfigField(
            type="string",
            label="Channel Override",
            placeholder="#downloads",
            required=False,
            help="Override default webhook channel",
        ),
        "username": ConfigField(
            type="string",
            label="Bot Username",
            placeholder="Corvin",
            required=False,
        ),
    }

    supported_events = [NOTIFY_DOWNLOAD, NOTIFY_DISCOVERED, NOTIFY_SYNC]

    def __init__(self, config: dict[str, Any]) -> None:
        self.webhook_url = config.get("webhook_url", "")
        self.channel = config.get("channel", "")
        self.username = config.get("username", "Corvin")

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        return self._send(f"*Download Complete*\n_{data.get('title', 'Unknown')}_")

    def on_video_discovered(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        count = data.get("count", 1)

        msg = (
            f"*{count} New Videos Discovered*\nIn _{list_name}_"
            if count > 1
            else f"*New Video*\n_{title}_ in _{list_name}_"
        )
        return self._send(msg)

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        list_name = data.get("list_name", "Unknown")
        new = data.get("new_videos", 0)
        msg = (
            f"*Sync Complete*\n_{list_name}_ - {new} new"
            if new
            else f"_{list_name}_ synced"
        )
        return self._send(msg)

    def _send(self, text: str) -> bool:
        if not self.webhook_url:
            return False

        payload: dict[str, Any] = {"text": text, "username": self.username}
        if self.channel:
            payload["channel"] = self.channel

        return self._safe_request("post", self.webhook_url, json=payload)

    def test_connection(self) -> tuple[bool, str]:
        if not self.webhook_url:
            return False, "Webhook URL required"

        try:
            payload = {
                "text": "*Test from Corvin*\nSlack integration working!",
                "username": self.username,
            }
            if self.channel:
                payload["channel"] = self.channel

            resp = self._post(self.webhook_url, json=payload)
            resp.raise_for_status()
            return True, "Test message sent"
        except Exception as e:
            return self._handle_error(e)
