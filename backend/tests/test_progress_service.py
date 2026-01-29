"""Tests for progress_service module."""

import time

from app.services import progress_service


class TestProgressService:
    """Tests for progress tracking functions."""

    def setup_method(self):
        """Clear progress store before each test."""
        with progress_service._lock:
            progress_service._store.clear()
            progress_service._timestamps.clear()

    def test_get_all_empty(self):
        """Should return empty dict when no progress entries."""
        result = progress_service.get_all()
        assert result == {}

    def test_mark_done(self):
        """Should mark video as completed with 100% progress."""
        progress_service.mark_done(123)

        result = progress_service.get_all()
        assert 123 in result
        assert result[123]["status"] == "completed"
        assert result[123]["percent"] == 100.0

    def test_mark_error(self):
        """Should mark video with error status."""
        progress_service.mark_error(456, "Download failed")

        result = progress_service.get_all()
        assert 456 in result
        assert result[456]["status"] == "error"
        assert result[456]["error"] == "Download failed"

    def test_create_hook_initialises_progress(self):
        """Should initialise progress when hook is created."""
        progress_service.create_hook(789)

        result = progress_service.get_all()
        assert 789 in result
        assert result[789]["status"] == "pending"
        assert result[789]["percent"] == 0.0

    def test_hook_updates_on_downloading(self):
        """Should update progress during download."""
        hook = progress_service.create_hook(100)

        hook(
            {
                "status": "downloading",
                "_percent_str": "50.5%",
                "_speed_str": "1MB/s",
                "eta": 30,
            }
        )

        result = progress_service.get_all()
        assert result[100]["status"] == "downloading"
        assert result[100]["percent"] == 50.5
        assert result[100]["speed"] == "1MB/s"
        assert result[100]["eta"] == 30

    def test_hook_updates_on_finished(self):
        """Should set processing status when download finishes."""
        hook = progress_service.create_hook(101)

        hook({"status": "finished"})

        result = progress_service.get_all()
        assert result[101]["status"] == "processing"
        assert result[101]["percent"] == 100.0

    def test_hook_updates_on_error(self):
        """Should set error status on download error."""
        hook = progress_service.create_hook(102)

        hook({"status": "error", "error": "Network timeout"})

        result = progress_service.get_all()
        assert result[102]["status"] == "error"
        assert result[102]["error"] == "Network timeout"

    def test_hook_handles_invalid_percent(self):
        """Should handle invalid percent string gracefully."""
        hook = progress_service.create_hook(103)

        hook({"status": "downloading", "_percent_str": "invalid"})

        result = progress_service.get_all()
        assert result[103]["percent"] == 0.0

    def test_stale_entries_cleaned_up(self):
        """Should clean up entries older than TTL."""
        progress_service.create_hook(200)

        # Manually set timestamp to be stale
        with progress_service._lock:
            progress_service._timestamps[200] = (
                time.time() - progress_service.TTL_SECONDS - 1
            )

        result = progress_service.get_all()
        assert 200 not in result

    def test_multiple_videos_tracked(self):
        """Should track multiple videos independently."""
        progress_service.mark_done(1)
        progress_service.mark_error(2, "Error")
        progress_service.create_hook(3)

        result = progress_service.get_all()
        assert len(result) == 3
        assert result[1]["status"] == "completed"
        assert result[2]["status"] == "error"
        assert result[3]["status"] == "pending"
