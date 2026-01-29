"""
In-memory progress tracking for video downloads.

Provides real-time download progress updates via SSE.
Progress data is stored in memory and automatically cleaned up after TTL expires.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from app.sse_hub import Channel, broadcast

_lock = threading.Lock()
_store: dict[int, "ProgressEntry"] = {}
_timestamps: dict[int, float] = {}

TTL_SECONDS = 300


@dataclass
class ProgressEntry:
    """Represents the progress state for a single video download."""

    video_id: int
    status: str = "queued"
    percent: float = 0.0
    speed: str | None = None
    eta: int | None = None
    error: str | None = None
    attempt: int | None = None
    max_attempts: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _update(video_id: int, entry: ProgressEntry) -> None:
    """Replace the progress entry for a video and broadcast the update."""
    with _lock:
        _store[video_id] = entry
        _timestamps[video_id] = time.time()
    broadcast(Channel.PROGRESS)


def _get(video_id: int) -> ProgressEntry | None:
    """Get the current progress entry for a video."""
    with _lock:
        return _store.get(video_id)


def get_all() -> dict[int, dict]:
    """
    Get all active progress entries, cleaning up stale ones.

    Returns:
        Dictionary mapping video_id to progress data.
    """
    with _lock:
        now = time.time()
        stale = [vid for vid, ts in _timestamps.items() if now - ts > TTL_SECONDS]
        for vid in stale:
            _store.pop(vid, None)
            _timestamps.pop(vid, None)

        return {vid: entry.to_dict() for vid, entry in _store.items()}


def clear(video_id: int) -> None:
    """
    Reset progress to queued state for a fresh retry.

    Called when user manually retries a failed download.
    Clears all state including attempt counters.
    """
    _update(video_id, ProgressEntry(video_id=video_id, status="queued"))


def mark_done(video_id: int) -> None:
    """Mark a download as successfully completed."""
    _update(
        video_id, ProgressEntry(video_id=video_id, status="completed", percent=100.0)
    )


def mark_error(video_id: int, error: str) -> None:
    """Mark a download as permanently failed."""
    _update(video_id, ProgressEntry(video_id=video_id, status="error", error=error))


def mark_retrying(video_id: int, attempt: int, max_attempts: int) -> None:
    """
    Mark a download as retrying after an internal failure.

    Called by the task queue when a download fails but will be retried.
    """
    _update(
        video_id,
        ProgressEntry(
            video_id=video_id,
            status="retrying",
            attempt=attempt,
            max_attempts=max_attempts,
        ),
    )


def create_hook(video_id: int) -> Callable[[dict], None]:
    """
    Create a yt-dlp progress hook for a video.

    Initialises progress tracking and returns a callback for yt-dlp updates.
    Preserves attempt info if this is a retry attempt (attempt > 1).

    Args:
        video_id: The video ID to track progress for.

    Returns:
        A callback function suitable for yt-dlp's progress_hooks option.
    """
    # Check if we're continuing a retry (attempt > 1)
    existing = _get(video_id)
    if existing and existing.attempt and existing.attempt > 1:
        attempt = existing.attempt
        max_attempts = existing.max_attempts
    else:
        attempt = None
        max_attempts = None

    # Initialise progress state
    _update(
        video_id,
        ProgressEntry(
            video_id=video_id,
            status="pending",
            attempt=attempt,
            max_attempts=max_attempts,
        ),
    )

    def on_progress(data: dict) -> None:
        """Handle yt-dlp progress updates."""
        status = data.get("status")
        current = _get(video_id)

        # Preserve attempt info across updates
        current_attempt = current.attempt if current else None
        current_max = current.max_attempts if current else None

        if status == "downloading":
            try:
                percent = float(data.get("_percent_str", "0").strip().rstrip("%"))
            except (ValueError, AttributeError):
                percent = 0.0

            _update(
                video_id,
                ProgressEntry(
                    video_id=video_id,
                    status="downloading",
                    percent=percent,
                    speed=data.get("_speed_str"),
                    eta=data.get("eta"),
                    attempt=current_attempt,
                    max_attempts=current_max,
                ),
            )

        elif status == "finished":
            _update(
                video_id,
                ProgressEntry(
                    video_id=video_id,
                    status="processing",
                    percent=100.0,
                    attempt=current_attempt,
                    max_attempts=current_max,
                ),
            )

        elif status == "error":
            _update(
                video_id,
                ProgressEntry(
                    video_id=video_id,
                    status="error",
                    error=str(data.get("error", "Unknown")),
                ),
            )

    return on_progress
