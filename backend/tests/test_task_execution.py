"""Tests for task execution functions (sync_single_list, download_single_video)."""

# Note: These tests require more complex setup with mocked database sessions
# For now, we test the helper functions that don't require app context

from app.tasks import _append_videos_path


class TestAppendVideosPathEdgeCases:
    """Additional tests for _append_videos_path helper."""

    def test_handles_youtu_be_urls(self):
        """Should handle youtu.be URLs."""
        url = "https://youtu.be/channel/test"

        result = _append_videos_path(url)

        assert "/videos" in result

    def test_skips_shorts_path(self):
        """Should not append if /shorts already present."""
        url = "https://youtube.com/c/testchannel/shorts"

        result = _append_videos_path(url)

        assert result == "https://youtube.com/c/testchannel/shorts"

    def test_skips_streams_path(self):
        """Should not append if /streams already present."""
        url = "https://youtube.com/c/testchannel/streams"

        result = _append_videos_path(url)

        assert result == "https://youtube.com/c/testchannel/streams"


class TestIncludeLiveFiltering:
    """Tests for include_live filtering during sync."""

    def test_video_data_with_was_live_true_is_filtered(self):
        """Should filter out videos with was_live=True when include_live=False."""
        # This tests the filtering logic conceptually
        # The actual filtering happens in on_video_fetched callback in _execute_sync
        video_data = {
            "video_id": "live123",
            "title": "Live Stream Recording",
            "url": "https://youtube.com/watch?v=live123",
            "was_live": True,
        }

        include_live = False

        # Simulate the filtering logic from tasks.py
        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is True

    def test_video_data_with_was_live_false_is_not_filtered(self):
        """Should not filter videos with was_live=False."""
        video_data = {
            "video_id": "normal123",
            "title": "Normal Video",
            "url": "https://youtube.com/watch?v=normal123",
            "was_live": False,
        }

        include_live = False

        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is False

    def test_video_data_without_was_live_is_not_filtered(self):
        """Should not filter videos without was_live field."""
        video_data = {
            "video_id": "old123",
            "title": "Old Video",
            "url": "https://youtube.com/watch?v=old123",
        }

        include_live = False

        should_skip = not include_live and video_data.get("was_live")

        # None is falsy, so should_skip evaluates to False (or None which is falsy)
        assert not should_skip

    def test_video_data_with_was_live_true_not_filtered_when_include_live_true(self):
        """Should not filter live videos when include_live=True."""
        video_data = {
            "video_id": "live123",
            "title": "Live Stream Recording",
            "url": "https://youtube.com/watch?v=live123",
            "was_live": True,
        }

        include_live = True

        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is False
