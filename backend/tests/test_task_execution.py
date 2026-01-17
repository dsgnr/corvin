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
