"""
Keeps track of all available notifiers (Plex, Jellyfin, Slack, etc.).

Notifiers are registered here at app startup (in __init__.py). The registry
stores the notifier classes (not instances) so they can be instantiated
later with the user's config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.notifications.notifier import BaseNotifier

logger = get_logger("notifications")


class NotifierRegistry:
    """Registry of available notifier classes."""

    _notifiers: dict[str, type[BaseNotifier]] = {}

    @classmethod
    def register(cls, notifier_cls: type[BaseNotifier]) -> None:
        cls._notifiers[notifier_cls.id] = notifier_cls
        logger.debug("Registered notifier: %s", notifier_cls.id)

    @classmethod
    def get(cls, notifier_id: str) -> type[BaseNotifier] | None:
        return cls._notifiers.get(notifier_id)

    @classmethod
    def all(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": n.id,
                "name": n.name,
                "config_schema": {k: v.to_dict() for k, v in n.config_schema.items()},
                "supported_events": [e.to_dict() for e in n.supported_events],
            }
            for n in cls._notifiers.values()
        ]
