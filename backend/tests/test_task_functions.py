"""Tests for task functions (enqueue, schedule, etc.)."""

from app.tasks import _append_videos_path


class TestAppendVideosPath:
    """Tests for _append_videos_path helper."""

    def test_appends_to_youtube_channel(self):
        """Should append /videos to YouTube channel URL."""
        url = "https://youtube.com/c/testchannel"

        result = _append_videos_path(url)

        assert result == "https://youtube.com/c/testchannel/videos"

    def test_handles_trailing_slash(self):
        """Should handle trailing slash."""
        url = "https://youtube.com/c/testchannel/"

        result = _append_videos_path(url)

        assert result == "https://youtube.com/c/testchannel/videos"

    def test_skips_if_already_has_videos(self):
        """Should not append if /videos already present."""
        url = "https://youtube.com/c/testchannel/videos"

        result = _append_videos_path(url)

        assert result == "https://youtube.com/c/testchannel/videos"

    def test_skips_non_youtube_urls(self):
        """Should not modify non-YouTube URLs."""
        url = "https://vimeo.com/channel/test"

        result = _append_videos_path(url)

        assert result == "https://vimeo.com/channel/test"
