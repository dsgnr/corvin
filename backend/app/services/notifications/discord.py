"""Discord webhook notifier."""

from typing import Any

from app.schemas.notifications import (
    NOTIFY_DISCOVERED,
    NOTIFY_DOWNLOAD,
    NOTIFY_SYNC,
    ConfigField,
)
from app.services.notifications.notifier import HTTPNotifier


class DiscordNotifier(HTTPNotifier):
    """Sends notifications to Discord via webhooks."""

    id = "discord"
    name = "Discord"

    config_schema = {
        "webhook_url": ConfigField(
            type="password",
            label="Webhook URL",
            placeholder="https://discord.com/api/webhooks/...",
            help="Discord webhook URL from channel settings",
        ),
        "username": ConfigField(
            type="string",
            label="Bot Username",
            placeholder="Corvin",
            required=False,
            help="Override the webhook's default username",
        ),
        "avatar_url": ConfigField(
            type="string",
            label="Avatar URL",
            placeholder="https://example.com/avatar.png",
            required=False,
            help="Override the webhook's default avatar",
        ),
    }

    supported_events = [NOTIFY_DOWNLOAD, NOTIFY_DISCOVERED, NOTIFY_SYNC]

    def __init__(self, config: dict[str, Any]) -> None:
        self.webhook_url = config.get("webhook_url", "")
        self.username = config.get("username", "") or "Corvin"
        self.avatar_url = config.get("avatar_url", "")

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send_embed(
            title="Download Complete",
            description=title,
            footer=list_name,
            colour=0x00FF00,  # Green
        )

    def on_video_discovered(self, data: dict[str, Any]) -> bool:
        title = data.get("title", "Unknown")
        list_name = data.get("list_name", "Unknown")
        return self._send_embed(
            title="New Video Discovered",
            description=title,
            footer=list_name,
            colour=0x0099FF,  # Blue
        )

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        list_name = data.get("list_name", "Unknown")
        new_videos = data.get("new_videos", 0)
        return self._send_embed(
            title="Sync Complete",
            description=f"{list_name}\n{new_videos} new videos",
            colour=0x9933FF,  # Purple
        )

    def _send_embed(
        self,
        title: str,
        description: str,
        colour: int = 0x5865F2,
        footer: str | None = None,
    ) -> bool:
        """Send a Discord embed message."""
        if not self.webhook_url:
            return False

        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": colour,
        }

        if footer:
            embed["footer"] = {"text": footer}

        payload: dict[str, Any] = {
            "username": self.username,
            "embeds": [embed],
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return self._safe_request("post", self.webhook_url, json=payload)

    def test_connection(self) -> tuple[bool, str]:
        if not self.webhook_url:
            return False, "Webhook URL is required"

        try:
            payload: dict[str, Any] = {
                "username": self.username,
                "embeds": [
                    {
                        "title": "Test from Corvin",
                        "description": "Discord integration working!",
                        "color": 0x00FF00,
                    }
                ],
            }

            if self.avatar_url:
                payload["avatar_url"] = self.avatar_url

            resp = self._post(self.webhook_url, json=payload)
            resp.raise_for_status()
            return True, "Test message sent"
        except Exception as e:
            return self._handle_error(e)
