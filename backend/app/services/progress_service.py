"""
Progress tracking for video downloads.
"""

import threading
import time

from app.core.helpers import _parse_percent

_lock = threading.Lock()
_store: dict[int, tuple[dict, float]] = {}

TTL_SECONDS = 300


def _update(video_id: int, **fields) -> None:
    with _lock:
        progress, _ = _store.get(video_id, ({}, 0))
        progress.update(video_id=video_id, **fields)
        _store[video_id] = (progress, time.time())


def _cleanup_stale() -> None:
    now = time.time()
    stale_ids = [vid for vid, (_, ts) in _store.items() if now - ts > TTL_SECONDS]
    for vid in stale_ids:
        del _store[vid]


def get(video_id: int) -> dict | None:
    with _lock:
        _cleanup_stale()
        entry = _store.get(video_id)
        return dict(entry[0]) if entry else None


def mark_done(video_id: int) -> None:
    _update(video_id, status="completed", percent=100.0)


def mark_error(video_id: int, error: str) -> None:
    _update(video_id, status="error", error=error)


def create_hook(video_id: int):
    """
    Create a yt-dlp progress hook for a video.
    """
    _update(video_id, status="pending", percent=0.0, speed=None, eta=None, error=None)

    def on_progress(data: dict) -> None:
        status = data.get("status")

        if status == "downloading":
            percent = _parse_percent(data.get("_percent_str", "0"))
            _update(
                video_id,
                status=status,
                percent=percent,
                speed=data.get("_speed_str"),
                eta=data.get("eta"),
            )

        if status == "finished":
            _update(video_id, status="processing", percent=100.0)

        if status == "error":
            mark_error(video_id, error=str(data.get("error", "Unknown")))

    return on_progress
