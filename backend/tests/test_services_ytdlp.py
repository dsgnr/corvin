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
    def test_extracts_thumbnails_list(self, mock_ydl_class):
        """Should include full thumbnails list in metadata."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        thumbnails = [
            {"id": "0", "url": "https://example.com/banner.jpg"},
            {"id": "avatar_uncropped", "url": "https://example.com/avatar.jpg"},
            {"id": "banner_uncropped", "url": "https://example.com/fanart.jpg"},
        ]
        mock_ydl.extract_info.return_value = {
            "title": "Test Channel",
            "thumbnails": thumbnails,
        }

        result = YtDlpService.extract_list_metadata("https://youtube.com/c/test")

        assert result["thumbnails"] == thumbnails

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
        assert result["labels"] == {}

    def test_parses_entry_with_labels(self):
        """Should parse video entry with metadata labels."""
        entry = {
            "id": "abc123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "acodec": "opus",
            "height": 2160,
            "audio_channels": 2,
            "dynamic_range": "HDR",
            "filesize_approx": 1073741824,
        }

        result = YtDlpService._parse_single_entry(entry)

        assert result["labels"]["acodec"] == "opus"
        assert result["labels"]["resolution"] == "2160p"
        assert result["labels"]["audio_channels"] == 2
        assert result["labels"]["dynamic_range"] == "HDR"
        assert result["labels"]["filesize_approx"] == 1073741824

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


class TestExtractLabels:
    """Tests for YtDlpService._extract_labels method."""

    def test_extracts_all_labels(self):
        """Should extract all available metadata labels."""
        info = {
            "acodec": "aac",
            "height": 1080,
            "audio_channels": 6,
            "dynamic_range": "SDR",
            "filesize_approx": 500000000,
        }

        result = YtDlpService._extract_labels(info)

        assert result["acodec"] == "aac"
        assert result["resolution"] == "1080p"
        assert result["audio_channels"] == 6
        assert result["dynamic_range"] == "SDR"
        assert result["filesize_approx"] == 500000000

    def test_handles_missing_fields(self):
        """Should only include available fields."""
        info = {
            "acodec": "opus",
            "height": 720,
        }

        result = YtDlpService._extract_labels(info)

        assert result["acodec"] == "opus"
        assert result["resolution"] == "720p"
        assert "audio_channels" not in result
        assert "dynamic_range" not in result
        assert "filesize_approx" not in result

    def test_handles_empty_info(self):
        """Should return empty dict for empty info."""
        result = YtDlpService._extract_labels({})

        assert result == {}

    def test_handles_none_values(self):
        """Should skip None values."""
        info = {
            "acodec": None,
            "height": 1080,
        }

        result = YtDlpService._extract_labels(info)

        assert "acodec" not in result
        assert result["resolution"] == "1080p"


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


class TestDownloadListArtwork:
    """Tests for YtDlpService.download_list_artwork method."""

    @patch("app.services.ytdlp_service.requests.get")
    def test_downloads_all_artwork(self, mock_get, tmp_path):
        """Should download fanart, poster, and banner from thumbnails."""
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        thumbnails = [
            {"id": "banner_uncropped", "url": "https://example.com/fanart.jpg"},
            {"id": "avatar_uncropped", "url": "https://example.com/poster.jpg"},
            {"id": "0", "url": "https://example.com/banner.jpg"},
        ]

        results = YtDlpService.download_list_artwork(thumbnails, tmp_path)

        assert results["fanart.jpg"] is True
        assert results["poster.jpg"] is True
        assert results["banner.jpg"] is True
        assert (tmp_path / "fanart.jpg").exists()
        assert (tmp_path / "poster.jpg").exists()
        assert (tmp_path / "banner.jpg").exists()

    @patch("app.services.ytdlp_service.requests.get")
    def test_handles_missing_thumbnails(self, mock_get, tmp_path):
        """Should return False for missing thumbnail IDs."""
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        thumbnails = [
            {"id": "banner_uncropped", "url": "https://example.com/fanart.jpg"},
        ]

        results = YtDlpService.download_list_artwork(thumbnails, tmp_path)

        assert results["fanart.jpg"] is True
        assert results["poster.jpg"] is False
        assert results["banner.jpg"] is False

    @patch("app.services.ytdlp_service.requests.get")
    def test_handles_download_failure(self, mock_get, tmp_path):
        """Should return False when download fails."""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        thumbnails = [
            {"id": "banner_uncropped", "url": "https://example.com/fanart.jpg"},
        ]

        results = YtDlpService.download_list_artwork(thumbnails, tmp_path)

        assert results["fanart.jpg"] is False

    def test_handles_empty_thumbnails(self, tmp_path):
        """Should return all False for empty thumbnails list."""
        results = YtDlpService.download_list_artwork([], tmp_path)

        assert results["fanart.jpg"] is False
        assert results["poster.jpg"] is False
        assert results["banner.jpg"] is False

    @patch("app.services.ytdlp_service.requests.get")
    def test_creates_output_directory(self, mock_get, tmp_path):
        """Should create output directory if it doesn't exist."""
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        thumbnails = [
            {"id": "0", "url": "https://example.com/banner.jpg"},
        ]
        nested_dir = tmp_path / "nested" / "dir"

        results = YtDlpService.download_list_artwork(thumbnails, nested_dir)

        assert results["banner.jpg"] is True
        assert (nested_dir / "banner.jpg").exists()


class TestDownloadImage:
    """Tests for YtDlpService._download_image method."""

    @patch("app.services.ytdlp_service.requests.get")
    def test_downloads_image(self, mock_get, tmp_path):
        """Should download and save image."""
        mock_response = MagicMock()
        mock_response.content = b"image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        output_path = tmp_path / "test.jpg"
        result = YtDlpService._download_image(
            "https://example.com/img.jpg", output_path
        )

        assert result is True
        assert output_path.exists()
        assert output_path.read_bytes() == b"image data"

    @patch("app.services.ytdlp_service.requests.get")
    def test_handles_http_error(self, mock_get, tmp_path):
        """Should return False on HTTP error."""
        import requests

        mock_get.side_effect = requests.RequestException("404 Not Found")

        output_path = tmp_path / "test.jpg"
        result = YtDlpService._download_image(
            "https://example.com/img.jpg", output_path
        )

        assert result is False
        assert not output_path.exists()
