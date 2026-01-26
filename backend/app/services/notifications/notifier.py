"""
Base classes for building notifiers.

All notifiers inherit from BaseNotifier (or HTTPNotifier for web APIs,
which inherits from BaseNotifier). This gives a consistent interface so
NotificationService can treat them all the same way. There a tons of
different notifiers out there, so we try to abstract them for simplicity.

BaseNotifier requires you to define:
    - id: Short name like "plex" or "slack" (used in DB keys)
    - name: Display name like "Plex Media Server" (shown in UI)
    - config_schema: Dict of ConfigField (what settings the user fills in)
    - supported_events: List of EventConfig (what events this handles)

When notify(Event.DOWNLOAD_COMPLETED, data) is called, it looks for
a method called on_download_completed(data) and calls it if found.
This means you just add on_<event_name> methods for events you handle.

When the notifier is registered, it will automagically show up in the UI as well.
"""

from __future__ import annotations

from typing import Any

import requests

from app.core.logging import get_logger
from app.schemas.notifications import ConfigField, Event, EventConfig

logger = get_logger("notifications")


class BaseNotifier:
    """
    Base class for notification implementations.

    Implement on_<event_name>(data) methods to handle events.
    """

    id: str = ""
    name: str = ""
    config_schema: dict[str, ConfigField] = {}
    supported_events: list[EventConfig] = []

    def __init__(self, config: dict[str, Any]) -> None:
        """Override to extract config values."""
        pass

    def notify(self, event: Event, data: dict[str, Any]) -> bool:
        """Dispatch to on_<event_name> handler if it exists."""
        handler = getattr(self, f"on_{event.value}", None)
        if callable(handler):
            return handler(data)
        return True

    def test_connection(self) -> tuple[bool, str]:
        """Test connectivity. Returns (success, message). Override in subclass."""
        return False, "Not implemented"

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in cls.config_schema.items()}

    @classmethod
    def get_supported_events(cls) -> list[dict[str, Any]]:
        return [e.to_dict() for e in cls.supported_events]


class HTTPNotifier(BaseNotifier):
    """Base for notifiers that make HTTP requests."""

    timeout: int = 10

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a GET request with default timeout."""
        kwargs.setdefault("timeout", self.timeout)
        return requests.get(url, **kwargs)

    def _post(self, url: str, **kwargs: Any) -> requests.Response:
        """Make a POST request with default timeout."""
        kwargs.setdefault("timeout", self.timeout)
        return requests.post(url, **kwargs)

    def _safe_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> bool:
        """
        Make an HTTP request with automatic error handling.

        Use this in on_<event> handlers for cleaner code. Logs errors
        and returns False on failure, True on success.

        Args:
            method: HTTP method ("get" or "post")
            url: Request URL
            **kwargs: Passed to requests

        Returns:
            True if request succeeded (2xx), False otherwise.
        """
        try:
            if method.lower() == "get":
                resp = self._get(url, **kwargs)
            else:
                resp = self._post(url, **kwargs)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("%s notification failed: %s", self.id, e)
            return False

    def _handle_error(self, e: Exception) -> tuple[bool, str]:
        """Convert exceptions to user-friendly messages."""
        if isinstance(e, requests.Timeout):
            return False, "Connection timed out"
        if isinstance(e, requests.ConnectionError):
            return False, "Could not connect to server"
        if isinstance(e, requests.HTTPError):
            status = e.response.status_code
            if status == 401:
                return False, "Invalid credentials"
            if status == 404:
                return False, "Endpoint not found"
            return False, f"HTTP error: {status}"
        return False, str(e)
