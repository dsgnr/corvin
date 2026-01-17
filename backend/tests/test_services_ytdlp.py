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


class TestExtractVideos:
    """Tests for YtDlpService.extract_videos method."""

    @patch.object(YtDlpService, "_fetch_metadata_parallel")
    @patch.object(YtDlpService, "_extract_video_entries")
    def test_extracts_videos_successfully(self, mock_entries, mock_parallel):
        """Should extract videos from URL."""
        mock_entries.return_value = [
            {"video_id": "abc123", "url": "https://youtube.com/watch?v=abc123"},
            {"video_id": "def456", "url": "https://youtube.com/watch?v=def456"},
        ]
        mock_parallel.return_value = [
            {"video_id": "abc123", "title": "Video 1"},
            {"video_id": "def456", "title": "Video 2"},
        ]

        result = YtDlpService.extract_videos("https://youtube.com/c/test")

        assert len(result) == 2
        mock_entries.assert_called_once()
        mock_parallel.assert_called_once()

    @patch.object(YtDlpService, "_extract_video_entries")
    def test_returns_empty_when_no_entries(self, mock_entries):
        """Should return empty list when no video entries found."""
        mock_entries.return_value = []

        result = YtDlpService.extract_videos("https://youtube.com/c/empty")

        assert result == []

    @patch.object(YtDlpService, "_fetch_metadata_parallel")
    @patch.object(YtDlpService, "_extract_video_entries")
    def test_filters_existing_videos(self, mock_entries, mock_parallel):
        """Should skip videos that already exist."""
        mock_entries.return_value = [
            {"video_id": "abc123", "url": "https://youtube.com/watch?v=abc123"},
            {"video_id": "existing", "url": "https://youtube.com/watch?v=existing"},
        ]
        mock_parallel.return_value = [{"video_id": "abc123", "title": "New Video"}]

        YtDlpService.extract_videos(
            "https://youtube.com/c/test",
            existing_video_ids={"existing"},
        )

        # Should only fetch metadata for non-existing video
        call_args = mock_parallel.call_args[0][0]
        assert len(call_args) == 1
        assert "abc123" in call_args[0]

    @patch.object(YtDlpService, "_fetch_metadata_parallel")
    @patch.object(YtDlpService, "_extract_video_entries")
    def test_calls_callback_for_each_video(self, mock_entries, mock_parallel):
        """Should call on_video_fetched callback for each video."""
        mock_entries.return_value = [
            {"video_id": "abc123", "url": "https://youtube.com/watch?v=abc123"},
        ]
        mock_parallel.return_value = [{"video_id": "abc123", "title": "Video 1"}]

        callback = MagicMock()
        YtDlpService.extract_videos(
            "https://youtube.com/c/test", on_video_fetched=callback
        )

        mock_parallel.assert_called_once()


class TestExtractVideoEntries:
    """Tests for YtDlpService._extract_video_entries method."""

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_extracts_flat_entries(self, mock_ydl_class):
        """Should extract video entries from flat playlist."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"id": "vid1", "webpage_url": "https://youtube.com/watch?v=vid1"},
                {"id": "vid2", "webpage_url": "https://youtube.com/watch?v=vid2"},
            ]
        }

        result = YtDlpService._extract_video_entries("https://youtube.com/c/test")

        assert len(result) == 2
        assert result[0]["video_id"] == "vid1"

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_handles_nested_entries(self, mock_ydl_class):
        """Should flatten nested entry groups (videos/shorts)."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "entries": [
                        {
                            "id": "vid1",
                            "webpage_url": "https://youtube.com/watch?v=vid1",
                        },
                    ]
                },
                {
                    "entries": [
                        {
                            "id": "short1",
                            "webpage_url": "https://youtube.com/shorts/short1",
                        },
                    ]
                },
            ]
        }

        result = YtDlpService._extract_video_entries("https://youtube.com/c/test")

        assert len(result) == 2

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_handles_empty_response(self, mock_ydl_class):
        """Should return empty list when no info returned."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = None

        result = YtDlpService._extract_video_entries("https://youtube.com/c/test")

        assert result == []

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_skips_entries_without_id_or_url(self, mock_ydl_class):
        """Should skip entries missing id or url."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"id": "vid1", "webpage_url": "https://youtube.com/watch?v=vid1"},
                {"id": "no_url"},
                {"webpage_url": "https://youtube.com/watch?v=no_id"},
                None,
            ]
        }

        result = YtDlpService._extract_video_entries("https://youtube.com/c/test")

        assert len(result) == 1


class TestFetchSingleVideo:
    """Tests for YtDlpService._fetch_single_video method."""

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_fetches_video_metadata(self, mock_ydl_class):
        """Should fetch and parse video metadata."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "upload_date": "20240115",
        }

        result = YtDlpService._fetch_single_video(
            "https://youtube.com/watch?v=abc123", None
        )

        assert result is not None
        assert result["video_id"] == "abc123"
        assert result["title"] == "Test Video"

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_filters_by_date(self, mock_ydl_class):
        """Should filter out videos before from_date."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "id": "old123",
            "title": "Old Video",
            "webpage_url": "https://youtube.com/watch?v=old123",
            "upload_date": "20230101",
        }

        result = YtDlpService._fetch_single_video(
            "https://youtube.com/watch?v=old123",
            "20240101",
        )

        assert result is None

    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_handles_extraction_error(self, mock_ydl_class):
        """Should return None on extraction error."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Network error")

        result = YtDlpService._fetch_single_video(
            "https://youtube.com/watch?v=abc123", None
        )

        assert result is None


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
            "ext": "mp4",
            "acodec": "aac",
            "height": 1080,
            "audio_channels": 6,
            "dynamic_range": "SDR",
            "filesize_approx": 500000000,
        }

        result = YtDlpService._extract_labels(info)

        assert result["format"] == "mp4"
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
        assert "format" not in result
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


class TestDownloadVideo:
    """Tests for YtDlpService.download_video method."""

    @patch("app.services.progress_service.create_hook")
    @patch("app.services.progress_service.mark_done")
    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_download_success(
        self,
        mock_ydl_class,
        mock_mark_done,
        mock_create_hook,
        app,
        sample_video,
        sample_profile,
    ):
        """Should download video successfully."""
        from app.extensions import db
        from app.models import Profile, Video

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Video",
            "ext": "mp4",
            "height": 1080,
        }
        mock_ydl.prepare_filename.return_value = "/downloads/test.mp4"
        mock_create_hook.return_value = MagicMock()

        with app.app_context():
            video = db.session.get(Video, sample_video)
            profile = db.session.get(Profile, sample_profile)

            with patch.object(YtDlpService, "write_video_nfo", return_value=True):
                success, result, labels = YtDlpService.download_video(video, profile)

        assert success is True
        assert result == "/downloads/test.mp4"
        assert labels.get("format") == "mp4"

    @patch("app.services.progress_service.create_hook")
    @patch("app.services.progress_service.mark_error")
    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_download_failure_no_info(
        self,
        mock_ydl_class,
        mock_mark_error,
        mock_create_hook,
        app,
        sample_video,
        sample_profile,
    ):
        """Should handle download failure when no info returned."""
        from app.extensions import db
        from app.models import Profile, Video

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = None
        mock_create_hook.return_value = MagicMock()

        with app.app_context():
            video = db.session.get(Video, sample_video)
            profile = db.session.get(Profile, sample_profile)

            success, result, labels = YtDlpService.download_video(video, profile)

        assert success is False
        assert "Failed to extract" in result

    @patch("app.services.progress_service.create_hook")
    @patch("app.services.progress_service.mark_error")
    @patch("app.services.ytdlp_service.yt_dlp.YoutubeDL")
    def test_download_error_exception(
        self,
        mock_ydl_class,
        mock_mark_error,
        mock_create_hook,
        app,
        sample_video,
        sample_profile,
    ):
        """Should handle yt-dlp download errors."""
        import yt_dlp

        from app.extensions import db
        from app.models import Profile, Video

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = yt_dlp.DownloadError("Video unavailable")
        mock_create_hook.return_value = MagicMock()

        with app.app_context():
            video = db.session.get(Video, sample_video)
            profile = db.session.get(Profile, sample_profile)

            success, result, labels = YtDlpService.download_video(video, profile)

        assert success is False
        assert "Video unavailable" in result


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


class TestWriteChannelNfo:
    """Tests for YtDlpService.write_channel_nfo method."""

    def test_writes_nfo_file(self, tmp_path):
        """Should write tvshow.nfo file."""
        metadata = {
            "name": "Test Channel",
            "description": "A test channel description",
            "extractor": "Youtube",
        }

        result = YtDlpService.write_channel_nfo(metadata, tmp_path, "UC123")

        assert result is True
        nfo_path = tmp_path / "tvshow.nfo"
        assert nfo_path.exists()

        content = nfo_path.read_text()
        assert "Test Channel" in content
        assert "A test channel description" in content
        assert "UC123" in content

    def test_creates_output_directory(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "channel"
        metadata = {"name": "Test"}

        result = YtDlpService.write_channel_nfo(metadata, nested_dir)

        assert result is True
        assert (nested_dir / "tvshow.nfo").exists()

    def test_handles_missing_metadata(self, tmp_path):
        """Should handle missing metadata gracefully."""
        metadata = {}

        result = YtDlpService.write_channel_nfo(metadata, tmp_path)

        assert result is True
        content = (tmp_path / "tvshow.nfo").read_text()
        assert "Unknown" in content


class TestWriteVideoNfo:
    """Tests for YtDlpService.write_video_nfo method."""

    def test_writes_video_nfo(self, app, sample_video, tmp_path):
        """Should write video NFO file."""
        from app.extensions import db
        from app.models import Video

        with app.app_context():
            video = db.session.get(Video, sample_video)
            video_path = str(tmp_path / "test_video.mp4")

            result = YtDlpService.write_video_nfo(video, video_path)

        assert result is True
        nfo_path = tmp_path / "test_video.nfo"
        assert nfo_path.exists()

        content = nfo_path.read_text()
        assert "Test Video" in content

    def test_includes_upload_date_info(self, app, sample_list, tmp_path):
        """Should include year and season from upload date."""
        from app.extensions import db
        from app.models import Video

        with app.app_context():
            video = Video(
                video_id="dated123",
                title="Dated Video",
                url="https://youtube.com/watch?v=dated123",
                list_id=sample_list,
                upload_date=datetime(2024, 6, 15),
                duration=300,
            )
            db.session.add(video)
            db.session.commit()

            video_path = str(tmp_path / "dated_video.mp4")
            result = YtDlpService.write_video_nfo(video, video_path)

        assert result is True
        content = (tmp_path / "dated_video.nfo").read_text()
        assert "2024" in content
        assert "<runtime>5</runtime>" in content  # 300 seconds = 5 minutes
