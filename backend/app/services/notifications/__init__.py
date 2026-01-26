"""
Notification service.

This module provides a notification system that runs when key events occur,
such as when a video download completes.

Supported actions include:
- Triggering media library scans in Plex or Jellyfin
- Sending messages to external services (Slack, Discord, ntfy, Gotify, etc.)

Overview
--------
When a download finishes, NotificationService.download_completed() is called.
The service:

1. Iterates over all registered notifier classes
2. Loads each notifier's configuration from the database
3. Instantiates each enabled notifier
4. Dispatches the event to the notifier via notifier.notify(event, data)

Each notifier's notify() method routes the event to a matching handler
(e.g., on_download_completed()) if one exists.

Architecture
------------
- BaseNotifier
    Abstract base class that defines the notifier interface.

- HTTPNotifier
    Convenience base class for HTTP-based notifiers.

- NotifierRegistry
    Central registry that stores all available notifier classes.

- NotificationService
    Entry point used by the application to dispatch events.

- Schemas (app/schemas/notifications.py)
    Define configuration fields and supported events for each notifier.

Basic Usage
-----------
    from app.services.notifications import NotificationService

    NotificationService.download_completed(
        "Video Title",
        "/path/to/file"
    )

Adding a New Notifier
--------------------
1. Create a new module in this directory (e.g., telegram.py)
2. Subclass HTTPNotifier (or BaseNotifier for non-HTTP implementations)
3. Define:
   - id
   - name
   - config_schema
   - supported_events
4. Implement:
   - __init__()
   - test_connection()
   - one or more on_<event>() handlers
5. Register the notifier with NotifierRegistry.register()
6. Add tests in tests/test_notifications.py

Configuration
-------------
Notifier configuration is stored in the database. Sensitive values such as
tokens or webhook URLs may also be provided via environment variables, e.g.:

- NOTIFICATION_PLEX_TOKEN
- NOTIFICATION_SLACK_WEBHOOK_URL
"""

from app.services.notifications.discord import DiscordNotifier
from app.services.notifications.gotify import GotifyNotifier
from app.services.notifications.jellyfin import JellyfinNotifier
from app.services.notifications.ntfy import NtfyNotifier
from app.services.notifications.plex import PlexNotifier
from app.services.notifications.registry import NotifierRegistry
from app.services.notifications.service import (
    NotificationService as NotificationService,
)
from app.services.notifications.slack import SlackNotifier

# Register notifiers
NotifierRegistry.register(PlexNotifier)
NotifierRegistry.register(JellyfinNotifier)
NotifierRegistry.register(SlackNotifier)
NotifierRegistry.register(DiscordNotifier)
NotifierRegistry.register(NtfyNotifier)
NotifierRegistry.register(GotifyNotifier)
