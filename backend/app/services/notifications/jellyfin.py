"""Jellyfin / Emby notifier."""

from typing import Any
from urllib.parse import urljoin

from app.core.logging import get_logger
from app.schemas.notifications import SCAN_ON_DOWNLOAD, SCAN_ON_SYNC, ConfigField
from app.services.notifications.notifier import HTTPNotifier

logger = get_logger("notifications.jellyfin")


class JellyfinNotifier(HTTPNotifier):
    """Triggers Jellyfin/Emby library scans on media events."""

    id = "jellyfin"
    name = "Jellyfin / Emby"

    config_schema = {
        "url": ConfigField(
            type="string", label="Server URL", placeholder="http://localhost:8096"
        ),
        "api_key": ConfigField(
            type="password",
            label="API Key",
            help="Generate in Dashboard > API Keys",
        ),
        "library_id": ConfigField(
            type="select",
            label="Library",
            placeholder="All libraries",
            required=False,
            help="Leave empty to scan all libraries",
            dynamic_options="libraries",
        ),
    }

    supported_events = [SCAN_ON_DOWNLOAD, SCAN_ON_SYNC]

    def __init__(self, config: dict[str, Any]) -> None:
        self.url = config.get("url", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.library_id = config.get("library_id")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        return self._scan()

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        return self._scan() if data.get("new_videos", 0) > 0 else True

    def _scan(self) -> bool:
        if not self.url or not self.api_key:
            return False

        try:
            resp = self._post(
                urljoin(self.url, "/Library/Refresh"),
                headers=self._headers,
            )
            resp.raise_for_status()
            logger.info("Jellyfin scan triggered")
            return True
        except Exception as e:
            logger.error("Jellyfin scan failed: %s", e)
            return False

    def test_connection(self) -> tuple[bool, str]:
        if not self.url:
            return False, "Server URL required"
        if not self.api_key:
            return False, "API key required"

        try:
            resp = self._get(urljoin(self.url, "/System/Info"), headers=self._headers)
            resp.raise_for_status()
            info = resp.json()
            return (
                True,
                f"Connected to {info.get('ServerName', 'server')} v{info.get('Version', '?')}",
            )
        except Exception as e:
            return self._handle_error(e)

    def get_libraries(self) -> list[dict[str, Any]]:
        """Fetch available libraries for the config UI."""
        if not self.url or not self.api_key:
            return []

        try:
            resp = self._get(
                urljoin(self.url, "/Library/VirtualFolders"),
                headers=self._headers,
            )
            resp.raise_for_status()
            return [
                {
                    "id": f.get("ItemId", f.get("Name")),
                    "title": f.get("Name"),
                    "type": f.get("CollectionType", "unknown"),
                }
                for f in resp.json()
            ]
        except Exception:
            return []
