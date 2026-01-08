"""
In-memory progress tracking for video downloads.
Single store, polled by one SSE endpoint.
"""

import threading
import time

_lock = threading.Lock()
_store: dict[int, dict] = {}  # video_id -> progress dict
_timestamps: dict[int, float] = {}  # video_id -> last update time

TTL_SECONDS = 300


def _set(video_id: int, **fields) -> None:
    with _lock:
        if video_id not in _store:
            _store[video_id] = {"video_id": video_id}
        _store[video_id].update(fields)
        _timestamps[video_id] = time.time()


def get_all() -> dict[int, dict]:
    """Get all active progress entries, cleaning up stale ones."""
    with _lock:
        now = time.time()
        stale = [vid for vid, ts in _timestamps.items() if now - ts > TTL_SECONDS]
        for vid in stale:
            _store.pop(vid, None)
            _timestamps.pop(vid, None)

        return {vid: dict(data) for vid, data in _store.items()}


def mark_done(video_id: int) -> None:
    _set(video_id, status="completed", percent=100.0)


def mark_error(video_id: int, error: str) -> None:
    _set(video_id, status="error", error=error)


def create_hook(video_id: int):
    """Create a yt-dlp progress hook for a video."""
    _set(video_id, status="pending", percent=0.0, speed=None, eta=None, error=None)

    def on_progress(data: dict) -> None:
        status = data.get("status")

        if status == "downloading":
            try:
                percent = float(data.get("_percent_str", "0").strip().rstrip("%"))
            except (ValueError, AttributeError):
                percent = 0.0

            _set(
                video_id,
                status="downloading",
                percent=percent,
                speed=data.get("_speed_str"),
                eta=data.get("eta"),
            )

        elif status == "finished":
            _set(video_id, status="processing", percent=100.0)

        elif status == "error":
            _set(video_id, status="error", error=str(data.get("error", "Unknown")))

    return on_progress
