"""Tests for YtDlpService."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.ytdlp_service import YtDlpService


class TestExtractListMetadata:
    """Tests for YtDlpService.extract_list_metadata method."""

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_extracts_metadata(self, mock_ydl_class):
        """Should extract channel/playlist metadata."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "title": "Test Channel",
            "description": "A test channel",
            "thumbnails": [{"url": "https://example.com/thumb.jpg"}],
            "tags": ["tech", "coding"],
            "extractor_key": "Youtube",
        }

        result = YtDlpService.extract_list_metadata("https://youtube.com/c/test")

        assert result["name"] == "Test Channel"
        assert result["description"] == "A test channel"
        assert result["extractor"] == "Youtube"

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_handles_empty_response(self, mock_ydl_class):
        """Should return empty dict when no info returned."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = None

        result = YtDlpService.extract_list_metadata("https://example.com")

        assert result == {}

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_raises_on_error(self, mock_ydl_class):
        """Should raise exception on extraction failure."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            YtDlpService.extract_list_metadata("https://example.com")


class TestGetBestThumbnail:
    """Tests for YtDlpService._get_best_thumbnail method."""

    def test_returns_last_thumbnail(self):
        """Should return last thumbnail (typically highest quality)."""
        thumbnails = [
            {"url": "https://example.com/small.jpg"},
            {"url": "https://example.com/large.jpg"},
        ]

        result = YtDlpService._get_best_thumbnail(thumbnails)

        assert result == "https://example.com/large.jpg"

    def test_handles_empty_list(self):
        """Should return None for empty list."""
        result = YtDlpService._get_best_thumbnail([])

        assert result is None

    def test_skips_thumbnails_without_url(self):
        """Should skip thumbnails without URL."""
        thumbnails = [
            {"url": "https://example.com/valid.jpg"},
            {"id": "no_url"},
        ]

        result = YtDlpService._get_best_thumbnail(thumbnails)

        assert result == "https://example.com/valid.jpg"


class TestParseUploadDate:
    """Tests for YtDlpService._parse_upload_date method."""

    def test_parses_valid_date(self):
        """Should parse YYYYMMDD format."""
        result = YtDlpService._parse_upload_date("20240115")

        assert result == datetime(2024, 1, 15)

    def test_handles_none(self):
        """Should return None for None input."""
        result = YtDlpService._parse_upload_date(None)

        assert result is None

    def test_handles_invalid_format(self):
        """Should return None for invalid format."""
        result = YtDlpService._parse_upload_date("invalid")

        assert result is None


class TestParseSingleEntry:
    """Tests for YtDlpService._parse_single_entry method."""

    def test_parses_entry(self):
        """Should parse video entry."""
        entry = {
            "id": "abc123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "duration": 300,
            "upload_date": "20240101",
            "thumbnail": "https://example.com/thumb.jpg",
            "description": "A test video",
            "extractor_key": "Youtube",
        }

        result = YtDlpService._parse_single_entry(entry)

        assert result["video_id"] == "abc123"
        assert result["title"] == "Test Video"
        assert result["duration"] == 300

    def test_returns_none_without_id(self):
        """Should return None if no video ID."""
        entry = {"title": "No ID Video"}

        result = YtDlpService._parse_single_entry(entry)

        assert result is None

    def test_falls_back_to_url_field(self):
        """Should use url field if webpage_url missing."""
        entry = {
            "id": "abc123",
            "title": "Test",
            "url": "https://example.com/video",
        }

        result = YtDlpService._parse_single_entry(entry)

        assert result["url"] == "https://example.com/video"


class TestBuildDownloadOpts:
    """Tests for YtDlpService._build_download_opts method."""

    def test_includes_profile_opts(self, app, sample_profile):
        """Should include profile options."""
        from app.extensions import db
        from app.models import Profile

        with app.app_context():
            profile = db.session.get(Profile, sample_profile)

            opts = YtDlpService._build_download_opts(profile, "/downloads/%(title)s")

            assert opts["outtmpl"] == "/downloads/%(title)s"
            assert opts["quiet"] is True
            assert "postprocessors" in opts
