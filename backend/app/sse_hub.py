"""
Event-driven SSE hub using asyncio pub/sub.
"""

import asyncio
from contextlib import asynccontextmanager
from enum import Enum


class Channel(str, Enum):
    """
    SSE notification channels.

    Each channel represents a category of events that clients can subscribe to.
    """

    LISTS = "lists"
    TASKS = "tasks"
    TASKS_STATS = "tasks:stats"
    PROGRESS = "progress"
    HISTORY = "history"

    @classmethod
    def list_videos(cls, list_id: int) -> str:
        """Channel for video updates within a specific list."""
        return f"list:{list_id}:videos"

    @classmethod
    def list_tasks(cls, list_id: int) -> str:
        """Channel for task updates within a specific list."""
        return f"list:{list_id}:tasks"

    @classmethod
    def list_history(cls, list_id: int) -> str:
        """Channel for history updates within a specific list."""
        return f"list:{list_id}:history"


class SSEHub:
    """
    Pub/sub hub for SSE event notifications.

    Manages subscriptions and dispatches notifications to connected clients.
    """

    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    @asynccontextmanager
    async def subscribe(self, channel: str):
        """
        Subscribe to a channel for notifications.

        Args:
            channel: The channel name to subscribe to.

        Yields:
            An asyncio.Queue that receives notifications.

        Example:
            async with hub.subscribe("tasks") as queue:
                while True:
                    await queue.get()
                    # Handle notification
        """
        # Capture the event loop on first subscription
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.setdefault(channel, set()).add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                if channel in self._subscribers:
                    self._subscribers[channel].discard(queue)
                    if not self._subscribers[channel]:
                        del self._subscribers[channel]

    def notify(self, *channels: str) -> None:
        """
        Notify subscribers on one or more channels.

        This method is thread-safe and can be called from any thread.

        Args:
            *channels: Channel names to notify.
        """
        if self._loop is None:
            return

        for channel in channels:
            try:
                self._loop.call_soon_threadsafe(self._dispatch, channel)
            except RuntimeError:
                # Loop is closed or not running
                pass

    def _dispatch(self, channel: str) -> None:
        """Dispatch notification to all subscribers on a channel."""
        if channel not in self._subscribers:
            return
        for queue in self._subscribers.get(channel, set()):
            try:
                queue.put_nowait(True)
            except asyncio.QueueFull:
                pass  # Drop if full - subscriber will catch up on next poll


# Global instance
hub = SSEHub()


def notify(*channels: str) -> None:
    """Convenience function to notify channels."""
    hub.notify(*channels)
