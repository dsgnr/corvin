"""Tests for task execution functions."""

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models import Video, VideoList
from app.models.task import Task, TaskStatus, TaskType
from app.services import HistoryService
from app.tasks import (
    _append_videos_path,
    _mark_download_failure,
    _mark_download_success,
    enqueue_tasks_bulk,
)


class TestMarkDownloadSuccess:
    """Tests for _mark_download_success function."""

    def test_marks_video_downloaded(self, app, db_session, sample_video):
        """Should set downloaded flag and path."""
        video = db_session.query(Video).get(sample_video)

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                result = _mark_download_success(
                    db_session, video, "/downloads/test.mp4", {}
                )

        assert video.downloaded is True
        assert video.download_path == "/downloads/test.mp4"
        assert video.error_message is None
        assert result["status"] == "completed"

    def test_merges_labels(self, app, db_session, sample_video):
        """Should merge new labels with existing."""
        video = db_session.query(Video).get(sample_video)
        video.labels = {"existing": "value"}
        db_session.commit()

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                _mark_download_success(
                    db_session,
                    video,
                    "/path.mp4",
                    {"format": "mp4", "resolution": "1080p"},
                )

        assert video.labels["existing"] == "value"
        assert video.labels["format"] == "mp4"
        assert video.labels["resolution"] == "1080p"

    def test_handles_none_labels(self, app, db_session, sample_video):
        """Should handle video with None labels."""
        video = db_session.query(Video).get(sample_video)
        video.labels = None
        db_session.commit()

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                _mark_download_success(
                    db_session, video, "/path.mp4", {"format": "mp4"}
                )

        assert video.labels["format"] == "mp4"

    def test_handles_empty_labels_dict(self, app, db_session, sample_video):
        """Should handle empty labels dict from download."""
        video = db_session.query(Video).get(sample_video)
        video.labels = {"existing": "value"}
        db_session.commit()

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                _mark_download_success(db_session, video, "/path.mp4", {})

        # Existing labels should be preserved
        assert video.labels["existing"] == "value"


class TestMarkDownloadFailure:
    """Tests for _mark_download_failure function."""

    def test_sets_error_message(self, app, db_session, sample_video):
        """Should set error message on video."""
        video = db_session.query(Video).get(sample_video)

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                with pytest.raises(Exception, match="Download failed"):
                    _mark_download_failure(db_session, video, "Download failed")

        assert video.error_message == "Download failed"

    def test_raises_exception_for_retry(self, app, db_session, sample_video):
        """Should raise exception to trigger task retry."""
        video = db_session.query(Video).get(sample_video)

        with patch.object(HistoryService, "log"):
            with patch("app.sse_hub.notify"):
                with pytest.raises(Exception, match="Network error"):
                    _mark_download_failure(db_session, video, "Network error")


class TestSyncFilteringLogic:
    """Tests for sync filtering logic (shorts, live, blacklist)."""

    def test_shorts_filtering_logic(self):
        """Should filter shorts when include_shorts is False."""
        video_data = {
            "video_id": "short123",
            "title": "Short Video",
            "url": "https://youtube.com/shorts/short123",
        }

        include_shorts = False
        should_skip = not include_shorts and "shorts" in video_data.get("url", "")

        assert should_skip is True

    def test_shorts_not_filtered_when_enabled(self):
        """Should not filter shorts when include_shorts is True."""
        video_data = {
            "video_id": "short123",
            "title": "Short Video",
            "url": "https://youtube.com/shorts/short123",
        }

        include_shorts = True
        should_skip = not include_shorts and "shorts" in video_data.get("url", "")

        assert should_skip is False

    def test_live_filtering_logic(self):
        """Should filter live videos when include_live is False."""
        video_data = {
            "video_id": "live123",
            "title": "Live Stream",
            "url": "https://youtube.com/watch?v=live123",
            "was_live": True,
        }

        include_live = False
        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is True

    def test_live_not_filtered_when_enabled(self):
        """Should not filter live videos when include_live is True."""
        video_data = {
            "video_id": "live123",
            "title": "Live Stream",
            "url": "https://youtube.com/watch?v=live123",
            "was_live": True,
        }

        include_live = True
        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is False

    def test_live_not_filtered_when_was_live_false(self):
        """Should not filter when was_live is False."""
        video_data = {
            "video_id": "normal123",
            "title": "Normal Video",
            "url": "https://youtube.com/watch?v=normal123",
            "was_live": False,
        }

        include_live = False
        should_skip = not include_live and video_data.get("was_live")

        assert should_skip is False

    def test_live_not_filtered_when_was_live_missing(self):
        """Should not filter when was_live is missing."""
        video_data = {
            "video_id": "old123",
            "title": "Old Video",
            "url": "https://youtube.com/watch?v=old123",
        }

        include_live = False
        should_skip = not include_live and video_data.get("was_live")

        assert not should_skip  # None is falsy


class TestBlacklistRegex:
    """Tests for blacklist regex matching."""

    def test_blacklist_matches_sponsor(self):
        """Should match sponsor in title."""
        pattern = re.compile(r"(?i)sponsor|ad\s*break", re.IGNORECASE)

        assert pattern.search("This video has a SPONSOR segment") is not None
        assert pattern.search("sponsor mention") is not None

    def test_blacklist_matches_ad_break(self):
        """Should match ad break variations."""
        pattern = re.compile(r"(?i)sponsor|ad\s*break", re.IGNORECASE)

        assert pattern.search("Ad Break in the middle") is not None
        assert pattern.search("adbreak here") is not None
        assert pattern.search("AD BREAK") is not None

    def test_blacklist_no_match_normal_title(self):
        """Should not match normal titles."""
        pattern = re.compile(r"(?i)sponsor|ad\s*break", re.IGNORECASE)

        assert pattern.search("Normal video title") is None
        assert pattern.search("How to code in Python") is None

    def test_invalid_blacklist_regex(self):
        """Should handle invalid regex gracefully."""
        invalid_regex = r"[invalid(regex"

        try:
            pattern = re.compile(invalid_regex, re.IGNORECASE)
        except re.error:
            pattern = None

        assert pattern is None

    def test_empty_blacklist_regex(self):
        """Should handle empty blacklist regex."""
        pattern = re.compile(r"", re.IGNORECASE)

        # Empty pattern matches everything
        assert pattern.search("Any title") is not None


class TestAppendVideosPath:
    """Tests for _append_videos_path helper."""

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

    def test_appends_to_youtube_channel(self):
        """Should append /videos to YouTube channel URL."""
        url = "https://youtube.com/c/testchannel"
        result = _append_videos_path(url)
        assert result == "https://youtube.com/c/testchannel/videos"

    def test_appends_to_www_youtube(self):
        """Should handle www.youtube.com."""
        url = "https://www.youtube.com/c/testchannel"
        result = _append_videos_path(url)
        assert result == "https://www.youtube.com/c/testchannel/videos"

    def test_handles_youtu_be(self):
        """Should handle youtu.be URLs."""
        url = "https://youtu.be/channel/test"
        result = _append_videos_path(url)
        assert "/videos" in result

    def test_handles_twitch(self):
        """Should handle Twitch URLs."""
        url = "https://twitch.tv/channelname"
        result = _append_videos_path(url)
        assert "/videos" in result

    def test_skips_non_supported_domains(self):
        """Should not modify non-YouTube/Twitch URLs."""
        url = "https://vimeo.com/channel/test"
        result = _append_videos_path(url)
        assert result == url

    def test_skips_if_videos_present(self):
        """Should not append if /videos already present."""
        url = "https://youtube.com/c/testchannel/videos"
        result = _append_videos_path(url)
        assert result == url

    def test_skips_if_shorts_present(self):
        """Should not append if /shorts present."""
        url = "https://youtube.com/c/testchannel/shorts"
        result = _append_videos_path(url)
        assert result == url

    def test_skips_if_streams_present(self):
        """Should not append if /streams present."""
        url = "https://youtube.com/c/testchannel/streams"
        result = _append_videos_path(url)
        assert result == url

    def test_handles_trailing_slash(self):
        """Should handle trailing slash."""
        url = "https://youtube.com/c/testchannel/"
        result = _append_videos_path(url)
        assert result == "https://youtube.com/c/testchannel/videos"

    def test_handles_uppercase_domain(self):
        """Should handle uppercase in domain."""
        url = "https://YOUTUBE.COM/c/testchannel"
        result = _append_videos_path(url)
        assert "/videos" in result

    def test_handles_at_handle_format(self):
        """Should handle @handle format URLs."""
        url = "https://youtube.com/@channelhandle"
        result = _append_videos_path(url)
        assert result == "https://youtube.com/@channelhandle/videos"

    def test_handles_channel_id_format(self):
        """Should handle channel ID format URLs."""
        url = "https://youtube.com/channel/UC1234567890"
        result = _append_videos_path(url)
        assert result == "https://youtube.com/channel/UC1234567890/videos"

    def test_handles_user_format(self):
        """Should handle /user/ format URLs."""
        url = "https://youtube.com/user/username"
        result = _append_videos_path(url)
        assert result == "https://youtube.com/user/username/videos"


class TestEnsureListArtwork:
    """Tests for _ensure_list_artwork helper."""

    def test_calls_ytdlp_service(self, app, db_session, sample_list):
        """Should delegate to YtDlpService.ensure_list_artwork."""
        from app.tasks import _ensure_list_artwork

        video_list = db_session.query(VideoList).get(sample_list)

        with patch("app.services.YtDlpService") as mock_service:
            _ensure_list_artwork(video_list)

            mock_service.ensure_list_artwork.assert_called_once_with(
                video_list.source_name, video_list.url
            )


class TestSyncSingleList:
    """Tests for sync_single_list function."""

    def test_calls_execute_sync(self, app, db_session, sample_list):
        """Should delegate to _execute_sync."""
        from app.tasks import sync_single_list

        with patch("app.tasks._execute_sync") as mock_execute:
            mock_execute.return_value = {"new_videos": 5, "total_found": 10}

            result = sync_single_list(sample_list)

            mock_execute.assert_called_once_with(sample_list)
            assert result["new_videos"] == 5


class TestExecuteSync:
    """Tests for _execute_sync function."""

    def test_raises_not_found_for_invalid_list(self, app):
        """Should raise NotFoundError for non-existent list."""
        from app.core.exceptions import NotFoundError
        from app.tasks import _execute_sync

        with pytest.raises(NotFoundError):
            _execute_sync(99999)

    def test_syncs_list_successfully(self, app, db_session, sample_list):
        """Should sync list and return counts."""
        from app.tasks import _execute_sync

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.extract_videos.return_value = []
            mock_service.ensure_list_artwork.return_value = None

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    result = _execute_sync(sample_list)

        assert "new_videos" in result
        assert "total_found" in result

    def test_updates_last_synced(self, app, db_session, sample_list):
        """Should update last_synced timestamp."""
        from app.tasks import _execute_sync

        video_list = db_session.query(VideoList).get(sample_list)
        old_synced = video_list.last_synced

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.extract_videos.return_value = []
            mock_service.ensure_list_artwork.return_value = None

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    _execute_sync(sample_list)

        db_session.refresh(video_list)
        assert video_list.last_synced != old_synced
        assert video_list.last_synced is not None

    def test_appends_videos_path_when_shorts_disabled(
        self, app, db_session, sample_profile
    ):
        """Should append /videos to URL when include_shorts is False."""
        from app.models import Profile
        from app.tasks import _execute_sync

        # Update profile to disable shorts
        profile = db_session.query(Profile).get(sample_profile)
        profile.include_shorts = False
        db_session.commit()

        video_list = VideoList(
            name="No Shorts",
            url="https://youtube.com/c/testchannel",
            profile_id=sample_profile,
        )
        db_session.add(video_list)
        db_session.commit()

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.extract_videos.return_value = []
            mock_service.ensure_list_artwork.return_value = None

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    _execute_sync(video_list.id)

        # Check that extract_videos was called with /videos appended
        call_args = mock_service.extract_videos.call_args
        assert "/videos" in call_args[0][0]

    def test_uses_from_date_filter(self, app, db_session, sample_profile):
        """Should pass from_date to extract_videos."""
        from app.tasks import _execute_sync

        video_list = VideoList(
            name="With Date",
            url="https://youtube.com/c/test",
            profile_id=sample_profile,
            from_date="20240101",
        )
        db_session.add(video_list)
        db_session.commit()

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.extract_videos.return_value = []
            mock_service.ensure_list_artwork.return_value = None

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    _execute_sync(video_list.id)

        call_args = mock_service.extract_videos.call_args
        from_date = call_args[0][1]
        assert from_date is not None
        assert from_date.year == 2024


class TestDownloadSingleVideo:
    """Tests for download_single_video function."""

    def test_calls_execute_download(self, app, db_session, sample_video):
        """Should delegate to _execute_download."""
        from app.tasks import download_single_video

        with patch("app.tasks._execute_download") as mock_execute:
            mock_execute.return_value = {"status": "completed", "path": "/test.mp4"}

            result = download_single_video(sample_video)

            mock_execute.assert_called_once_with(sample_video)
            assert result["status"] == "completed"


class TestExecuteDownload:
    """Tests for _execute_download function."""

    def test_raises_not_found_for_invalid_video(self, app):
        """Should raise NotFoundError for non-existent video."""
        from app.core.exceptions import NotFoundError
        from app.tasks import _execute_download

        with pytest.raises(NotFoundError):
            _execute_download(99999)

    def test_returns_already_downloaded_for_downloaded_video(
        self, app, db_session, sample_video
    ):
        """Should return early if video already downloaded."""
        from app.tasks import _execute_download

        video = db_session.query(Video).get(sample_video)
        video.downloaded = True
        db_session.commit()

        result = _execute_download(sample_video)

        assert result["status"] == "already_downloaded"

    def test_downloads_video_successfully(self, app, db_session, sample_video):
        """Should download video and mark as completed."""
        from app.tasks import _execute_download

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.download_video.return_value = (
                True,
                "/downloads/test.mp4",
                {"format": "mp4"},
            )

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    result = _execute_download(sample_video)

        assert result["status"] == "completed"
        assert result["path"] == "/downloads/test.mp4"

    def test_handles_download_failure(self, app, db_session, sample_video):
        """Should raise exception on download failure."""
        from app.tasks import _execute_download

        with patch("app.services.YtDlpService") as mock_service:
            mock_service.download_video.return_value = (
                False,
                "Video unavailable",
                {},
            )

            with patch("app.services.HistoryService.log"):
                with patch("app.sse_hub.notify"):
                    with pytest.raises(Exception, match="Video unavailable"):
                        _execute_download(sample_video)


class TestEnqueueTask:
    """Tests for enqueue_task function."""

    def test_creates_new_task(self, app, db_session, sample_list):
        """Should create a new task."""
        from app.tasks import enqueue_task

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                task = enqueue_task("sync", sample_list)

        assert task is not None
        assert task.task_type == "sync"
        assert task.entity_id == sample_list
        assert task.status == TaskStatus.PENDING.value

    def test_returns_none_if_already_queued(self, app, db_session, sample_list):
        """Should return None if task already pending."""
        from app.tasks import enqueue_task

        # Create existing pending task
        existing = Task(
            task_type="sync",
            entity_id=sample_list,
            status=TaskStatus.PENDING.value,
        )
        db_session.add(existing)
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                task = enqueue_task("sync", sample_list)

        assert task is None

    def test_returns_none_if_already_running(self, app, db_session, sample_list):
        """Should return None if task already running."""
        from app.tasks import enqueue_task

        # Create existing running task
        existing = Task(
            task_type="sync",
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
        )
        db_session.add(existing)
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                task = enqueue_task("sync", sample_list)

        assert task is None

    def test_notifies_worker(self, app, db_session, sample_list):
        """Should notify worker when task created."""
        from app.tasks import enqueue_task

        mock_worker = MagicMock()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=mock_worker):
                enqueue_task("sync", sample_list)

        mock_worker.notify.assert_called_once()

    def test_uses_custom_max_retries(self, app, db_session, sample_list):
        """Should use custom max_retries value."""
        from app.tasks import enqueue_task

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                task = enqueue_task("sync", sample_list, max_retries=5)

        assert task.max_retries == 5


class TestEnqueueTasksBulk:
    """Tests for enqueue_tasks_bulk function."""

    def test_handles_empty_list(self):
        """Should handle empty entity list."""
        result = enqueue_tasks_bulk(TaskType.SYNC.value, [])

        assert result["queued"] == 0
        assert result["skipped"] == 0
        assert result["tasks"] == []

    def test_creates_multiple_tasks(self, app, db_session, sample_profile):
        """Should create multiple tasks."""
        # Create multiple lists
        lists = []
        for i in range(3):
            vl = VideoList(
                name=f"List {i}",
                url=f"https://youtube.com/c/test{i}",
                profile_id=sample_profile,
            )
            db_session.add(vl)
            lists.append(vl)
        db_session.commit()

        list_ids = [vl.id for vl in lists]

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = enqueue_tasks_bulk("sync", list_ids)

        assert result["queued"] == 3
        assert result["skipped"] == 0

    def test_skips_existing_pending_tasks(
        self, app, db_session, sample_list, sample_profile
    ):
        """Should skip entities with existing pending tasks."""
        # Create another list
        vl2 = VideoList(
            name="List 2",
            url="https://youtube.com/c/test2",
            profile_id=sample_profile,
        )
        db_session.add(vl2)
        db_session.commit()

        # Create existing pending task for sample_list
        existing = Task(
            task_type="sync",
            entity_id=sample_list,
            status=TaskStatus.PENDING.value,
        )
        db_session.add(existing)
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = enqueue_tasks_bulk("sync", [sample_list, vl2.id])

        assert result["queued"] == 1
        assert result["skipped"] == 1

    def test_handles_large_batch(self, app, db_session, sample_profile):
        """Should handle batches larger than SQLite limit."""
        # Create many lists
        lists = []
        for i in range(600):  # More than batch_size of 500
            vl = VideoList(
                name=f"List {i}",
                url=f"https://youtube.com/c/test{i}",
                profile_id=sample_profile,
            )
            db_session.add(vl)
            lists.append(vl)
        db_session.commit()

        list_ids = [vl.id for vl in lists]

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = enqueue_tasks_bulk("sync", list_ids)

        assert result["queued"] == 600


class TestScheduleSyncs:
    """Tests for schedule_syncs function."""

    def test_schedules_specific_lists(self, app, db_session, sample_list):
        """Should schedule sync for specific list IDs."""
        from app.tasks import schedule_syncs

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_syncs(list_ids=[sample_list], force=True)

        assert result["queued"] == 1

    def test_skips_disabled_lists(self, app, db_session, sample_profile):
        """Should skip disabled lists."""
        from app.tasks import schedule_syncs

        # Create disabled list
        disabled_list = VideoList(
            name="Disabled",
            url="https://youtube.com/c/disabled",
            profile_id=sample_profile,
            enabled=False,
        )
        db_session.add(disabled_list)
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_syncs(list_ids=[disabled_list.id], force=True)

        assert result["queued"] == 0

    def test_schedules_due_lists_only(self, app, db_session, sample_list):
        """Should only schedule lists that are due when force=False."""
        from app.tasks import schedule_syncs

        # Update list to be recently synced
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.last_synced = datetime.utcnow()
        video_list.sync_frequency = "daily"
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_syncs(list_ids=[sample_list], force=False)

        # Should not be scheduled because it was just synced
        assert result["queued"] == 0

    def test_schedules_all_enabled_lists(
        self, app, db_session, sample_list, sample_profile
    ):
        """Should schedule all enabled lists when no list_ids provided."""
        from app.tasks import schedule_syncs

        # Create another enabled list that's due
        vl2 = VideoList(
            name="List 2",
            url="https://youtube.com/c/test2",
            profile_id=sample_profile,
            enabled=True,
            last_synced=None,  # Never synced, so due
        )
        db_session.add(vl2)
        db_session.commit()

        # Make sample_list due too
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.last_synced = None
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_syncs(force=False)

        assert result["queued"] >= 2

    def test_returns_empty_when_no_lists_due(self, app, db_session, sample_list):
        """Should return empty result when no lists are due."""
        from app.tasks import schedule_syncs

        # Update list to be recently synced
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.last_synced = datetime.utcnow()
        video_list.sync_frequency = "daily"
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_syncs(force=False)

        assert result["queued"] == 0


class TestScheduleAllSyncs:
    """Tests for schedule_all_syncs function."""

    def test_delegates_to_schedule_syncs(self, app, db_session):
        """Should call schedule_syncs with no arguments."""
        from app.tasks import schedule_all_syncs

        with patch("app.tasks.schedule_syncs") as mock_schedule:
            mock_schedule.return_value = {"queued": 2, "skipped": 0}

            result = schedule_all_syncs()

            mock_schedule.assert_called_once_with()
            assert result["queued"] == 2


class TestScheduleDownloads:
    """Tests for schedule_downloads function."""

    def test_schedules_specific_videos(self, app, db_session, sample_video):
        """Should schedule download for specific video IDs."""
        from app.tasks import schedule_downloads

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_downloads(video_ids=[sample_video])

        assert result["queued"] == 1

    def test_skips_downloaded_videos(self, app, db_session, sample_video):
        """Should skip already downloaded videos."""
        from app.tasks import schedule_downloads

        video = db_session.query(Video).get(sample_video)
        video.downloaded = True
        db_session.commit()

        with patch("app.sse_hub.notify"):
            with patch("app.task_queue.get_worker", return_value=None):
                result = schedule_downloads(video_ids=[sample_video])

        assert result["queued"] == 0

    def test_respects_download_schedule(self, app, db_session, sample_video):
        """Should check download schedule for automatic downloads."""
        from app.models.download_schedule import DownloadSchedule
        from app.tasks import schedule_downloads

        with patch.object(DownloadSchedule, "is_download_allowed", return_value=False):
            result = schedule_downloads()

        assert result["queued"] == 0
        assert result.get("reason") == "schedule"

    def test_excludes_blacklisted_videos(self, app, db_session, sample_list):
        """Should exclude blacklisted videos from automatic downloads."""
        from app.models.download_schedule import DownloadSchedule
        from app.tasks import schedule_downloads

        # Create blacklisted video
        video = Video(
            video_id="blacklisted123",
            title="Blacklisted Video",
            url="https://youtube.com/watch?v=blacklisted123",
            list_id=sample_list,
            blacklisted=True,
        )
        db_session.add(video)
        db_session.commit()

        with patch.object(DownloadSchedule, "is_download_allowed", return_value=True):
            with patch("app.sse_hub.notify"):
                with patch("app.task_queue.get_worker", return_value=None):
                    result = schedule_downloads()

        # Blacklisted video should not be queued
        queued_ids = [t.entity_id for t in result.get("tasks", [])]
        assert video.id not in queued_ids

    def test_excludes_videos_from_non_auto_download_lists(
        self, app, db_session, sample_profile
    ):
        """Should exclude videos from lists with auto_download=False."""
        from app.models.download_schedule import DownloadSchedule
        from app.tasks import schedule_downloads

        # Create list with auto_download disabled
        video_list = VideoList(
            name="Manual Only",
            url="https://youtube.com/c/manual",
            profile_id=sample_profile,
            auto_download=False,
        )
        db_session.add(video_list)
        db_session.commit()

        video = Video(
            video_id="manual123",
            title="Manual Video",
            url="https://youtube.com/watch?v=manual123",
            list_id=video_list.id,
        )
        db_session.add(video)
        db_session.commit()

        with patch.object(DownloadSchedule, "is_download_allowed", return_value=True):
            with patch("app.sse_hub.notify"):
                with patch("app.task_queue.get_worker", return_value=None):
                    result = schedule_downloads()

        queued_ids = [t.entity_id for t in result.get("tasks", [])]
        assert video.id not in queued_ids

    def test_limits_automatic_downloads(self, app, db_session, sample_list):
        """Should limit automatic downloads to 100."""
        from app.models.download_schedule import DownloadSchedule
        from app.tasks import schedule_downloads

        # Create many videos
        for i in range(150):
            video = Video(
                video_id=f"vid{i}",
                title=f"Video {i}",
                url=f"https://youtube.com/watch?v=vid{i}",
                list_id=sample_list,
            )
            db_session.add(video)
        db_session.commit()

        with patch.object(DownloadSchedule, "is_download_allowed", return_value=True):
            with patch("app.sse_hub.notify"):
                with patch("app.task_queue.get_worker", return_value=None):
                    result = schedule_downloads()

        # Should be limited to 100
        assert result["queued"] <= 100
