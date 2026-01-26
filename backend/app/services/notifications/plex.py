"""Plex Media Server notifier."""

from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from app.core.logging import get_logger
from app.schemas.notifications import SCAN_ON_DOWNLOAD, SCAN_ON_SYNC, ConfigField
from app.services.notifications.notifier import HTTPNotifier

logger = get_logger("notifications.plex")


class PlexNotifier(HTTPNotifier):
    """Triggers Plex library scans on media events."""

    id = "plex"
    name = "Plex Media Server"

    config_schema = {
        "url": ConfigField(
            type="string", label="Server URL", placeholder="http://localhost:32400"
        ),
        "token": ConfigField(
            type="password",
            label="Plex Token",
            help="Find at support.plex.tv/articles/204059436",
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
        self.token = config.get("token", "")
        self.library_id = config.get("library_id")

    def on_download_completed(self, data: dict[str, Any]) -> bool:
        return self._scan()

    def on_sync_completed(self, data: dict[str, Any]) -> bool:
        return self._scan() if data.get("new_videos", 0) > 0 else True

    def _scan(self) -> bool:
        if not self.url or not self.token:
            return False

        try:
            section = f"/{self.library_id}" if self.library_id else "/all"
            resp = self._get(
                urljoin(self.url, f"/library/sections{section}/refresh"),
                params={"X-Plex-Token": self.token},
            )
            resp.raise_for_status()
            logger.info("Plex scan triggered")
            return True
        except Exception as e:
            logger.error("Plex scan failed: %s", e)
            return False

    def test_connection(self) -> tuple[bool, str]:
        if not self.url:
            return False, "Server URL required"
        if not self.token:
            return False, "Token required"

        try:
            resp = self._get(self.url, params={"X-Plex-Token": self.token})
            resp.raise_for_status()
            return True, "Connected to Plex"
        except Exception as e:
            return self._handle_error(e)

    def get_libraries(self) -> list[dict[str, Any]]:
        """Fetch available libraries for the config UI."""
        if not self.url or not self.token:
            return []

        try:
            resp = self._get(
                urljoin(self.url, "/library/sections"),
                params={"X-Plex-Token": self.token},
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            return [
                {"id": d.get("key"), "title": d.get("title"), "type": d.get("type")}
                for d in root.findall(".//Directory")
            ]
        except Exception:
            return []
