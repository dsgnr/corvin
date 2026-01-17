"""Tests for task execution functions (sync_single_list, download_single_video)."""

from unittest.mock import patch

import pytest

from app.core.exceptions import NotFoundError


class TestSyncSingleList:
    """Tests for sync_single_list and _execute_sync functions."""

    @patch("app.services.ytdlp_service.YtDlpService.extract_videos")
    @patch("app.services.history_service.HistoryService.log")
    def test_sync_list_success(self, mock_history, mock_extract, app, sample_list):
        """Should sync videos for a list."""
        from app.tasks import sync_single_list

        mock_extract.return_value = []  # No new videos

        with app.app_context():
            result = sync_single_list(app, sample_list)

        assert result["new_videos"] == 0
        assert mock_history.call_count >= 2  # sync started + synced

    def test_sync_list_not_found(self, app):
        """Should raise NotFoundError for non-existent list."""
        from app.tasks import sync_single_list

        with pytest.raises(NotFoundError):
            sync_single_list(app, 99999)

    @patch("app.services.ytdlp_service.YtDlpService.extract_videos")
    @patch("app.services.history_service.HistoryService.log")
    def test_sync_updates_last_synced(
        self, mock_history, mock_extract, app, sample_list
    ):
        """Should update last_synced timestamp."""
        from app.extensions import db
        from app.models import VideoList
        from app.tasks import sync_single_list

        mock_extract.return_value = []

        with app.app_context():
            video_list = db.session.get(VideoList, sample_list)
            old_synced = video_list.last_synced

            sync_single_list(app, sample_list)

            db.session.refresh(video_list)
            assert video_list.last_synced is not None
            if old_synced:
                assert video_list.last_synced > old_synced

    @patch("app.services.ytdlp_service.YtDlpService.extract_videos")
    @patch("app.services.history_service.HistoryService.log")
    def test_sync_appends_videos_path_when_shorts_disabled(
        self, mock_history, mock_extract, app, sample_list, sample_profile
    ):
        """Should append /videos to URL when include_shorts is disabled."""
        from app.extensions import db
        from app.models import Profile
        from app.tasks import sync_single_list

        mock_extract.return_value = []

        with app.app_context():
            profile = db.session.get(Profile, sample_profile)
            profile.include_shorts = False
            db.session.commit()

            sync_single_list(app, sample_list)

            # Check that extract_videos was called with /videos appended
            call_url = mock_extract.call_args[0][0]
            assert "/videos" in call_url


class TestDownloadSingleVideo:
    """Tests for download_single_video and _execute_download functions."""

    @patch("app.services.ytdlp_service.YtDlpService.download_video")
    @patch("app.services.history_service.HistoryService.log")
    def test_download_video_success(
        self, mock_history, mock_download, app, sample_video
    ):
        """Should download video successfully."""
        from app.tasks import download_single_video

        mock_download.return_value = (True, "/downloads/video.mp4", {"format": "mp4"})

        with app.app_context():
            result = download_single_video(app, sample_video)

        assert result["status"] == "completed"
        assert result["path"] == "/downloads/video.mp4"

    def test_download_video_not_found(self, app):
        """Should raise NotFoundError for non-existent video."""
        from app.tasks import download_single_video

        with pytest.raises(NotFoundError):
            download_single_video(app, 99999)

    def test_download_already_downloaded(self, app, sample_video):
        """Should skip already downloaded videos."""
        from app.extensions import db
        from app.models import Video
        from app.tasks import download_single_video

        with app.app_context():
            video = db.session.get(Video, sample_video)
            video.downloaded = True
            db.session.commit()

            result = download_single_video(app, sample_video)

        assert result["status"] == "already_downloaded"

    @patch("app.services.ytdlp_service.YtDlpService.download_video")
    @patch("app.services.history_service.HistoryService.log")
    def test_download_failure(self, mock_history, mock_download, app, sample_video):
        """Should handle download failure."""
        from app.tasks import download_single_video

        mock_download.return_value = (False, "Network error", {})

        with app.app_context():
            with pytest.raises(Exception, match="Network error"):
                download_single_video(app, sample_video)


class TestMarkDownloadSuccess:
    """Tests for _mark_download_success function."""

    @patch("app.services.history_service.HistoryService.log")
    def test_marks_video_downloaded(self, mock_history, app, sample_video):
        """Should mark video as downloaded with path."""
        from app.extensions import db
        from app.models import Video
        from app.tasks import _mark_download_success

        with app.app_context():
            video = db.session.get(Video, sample_video)

            result = _mark_download_success(video, "/downloads/test.mp4", {})

            db.session.refresh(video)
            assert video.downloaded is True
            assert video.download_path == "/downloads/test.mp4"
            assert video.error_message is None
            assert result["status"] == "completed"

    @patch("app.services.history_service.HistoryService.log")
    def test_updates_labels(self, mock_history, app, sample_video):
        """Should update video labels."""
        from app.extensions import db
        from app.models import Video
        from app.tasks import _mark_download_success

        with app.app_context():
            video = db.session.get(Video, sample_video)
            video.labels = {"existing": "value"}
            db.session.commit()

            _mark_download_success(
                video, "/downloads/test.mp4", {"format": "mp4", "resolution": "1080p"}
            )

            db.session.refresh(video)
            assert video.labels["existing"] == "value"
            assert video.labels["format"] == "mp4"
            assert video.labels["resolution"] == "1080p"


class TestMarkDownloadFailure:
    """Tests for _mark_download_failure function."""

    @patch("app.services.history_service.HistoryService.log")
    def test_marks_video_with_error(self, mock_history, app, sample_video):
        """Should set error message on video."""
        from app.extensions import db
        from app.models import Video
        from app.tasks import _mark_download_failure

        with app.app_context():
            video = db.session.get(Video, sample_video)

            with pytest.raises(Exception, match="Download failed"):
                _mark_download_failure(video, "Download failed")

            db.session.refresh(video)
            assert video.error_message == "Download failed"
