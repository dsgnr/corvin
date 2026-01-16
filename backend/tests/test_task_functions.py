"""Tests for task functions (enqueue, schedule, etc.)."""

from app.extensions import db
from app.models import Video, VideoList
from app.models.task import TaskStatus, TaskType
from app.tasks import (
    _append_videos_path,
    enqueue_task,
    enqueue_tasks_bulk,
    schedule_downloads,
    schedule_syncs,
)


class TestEnqueueTask:
    """Tests for enqueue_task function."""

    def test_creates_task(self, app, sample_list):
        """Should create a new task."""
        with app.app_context():
            task = enqueue_task(TaskType.SYNC.value, sample_list)

            assert task is not None
            assert task.task_type == "sync"
            assert task.entity_id == sample_list
            assert task.status == TaskStatus.PENDING.value

    def test_returns_none_if_already_pending(self, app, sample_list):
        """Should return None if task already pending."""
        with app.app_context():
            enqueue_task(TaskType.SYNC.value, sample_list)
            result = enqueue_task(TaskType.SYNC.value, sample_list)

            assert result is None

    def test_returns_none_if_already_running(self, app, sample_list):
        """Should return None if task already running."""
        with app.app_context():
            task = enqueue_task(TaskType.SYNC.value, sample_list)
            task.status = TaskStatus.RUNNING.value
            db.session.commit()

            result = enqueue_task(TaskType.SYNC.value, sample_list)

            assert result is None

    def test_allows_new_task_after_completion(self, app, sample_list):
        """Should allow new task after previous completed."""
        with app.app_context():
            task = enqueue_task(TaskType.SYNC.value, sample_list)
            task.status = TaskStatus.COMPLETED.value
            db.session.commit()

            result = enqueue_task(TaskType.SYNC.value, sample_list)

            assert result is not None


class TestEnqueueTasksBulk:
    """Tests for enqueue_tasks_bulk function."""

    def test_creates_multiple_tasks(self, app, sample_list, sample_video):
        """Should create multiple tasks."""
        with app.app_context():
            result = enqueue_tasks_bulk(
                TaskType.DOWNLOAD.value, [sample_video, sample_video + 100]
            )

            assert result["queued"] == 2
            assert result["skipped"] == 0

    def test_skips_existing_tasks(self, app, sample_video):
        """Should skip already queued tasks."""
        with app.app_context():
            enqueue_task(TaskType.DOWNLOAD.value, sample_video)

            result = enqueue_tasks_bulk(TaskType.DOWNLOAD.value, [sample_video])

            assert result["queued"] == 0
            assert result["skipped"] == 1

    def test_returns_empty_for_no_ids(self, app):
        """Should handle empty list."""
        with app.app_context():
            result = enqueue_tasks_bulk(TaskType.SYNC.value, [])

            assert result["queued"] == 0
            assert result["skipped"] == 0


class TestScheduleSyncs:
    """Tests for schedule_syncs function."""

    def test_schedules_specific_lists(self, app, sample_list):
        """Should schedule syncs for specified list IDs."""
        with app.app_context():
            result = schedule_syncs([sample_list])

            assert result["queued"] == 1

    def test_skips_disabled_lists(self, app, sample_list):
        """Should skip disabled lists."""
        with app.app_context():
            video_list = db.session.get(VideoList, sample_list)
            video_list.enabled = False
            db.session.commit()

            result = schedule_syncs([sample_list])

            assert result["queued"] == 0

    def test_schedules_due_lists(self, app, sample_list):
        """Should schedule all due lists when no IDs provided."""
        with app.app_context():
            # List has never been synced, so it's due
            result = schedule_syncs()

            assert result["queued"] == 1


class TestScheduleDownloads:
    """Tests for schedule_downloads function."""

    def test_schedules_specific_videos(self, app, sample_video):
        """Should schedule downloads for specified video IDs."""
        with app.app_context():
            result = schedule_downloads([sample_video])

            assert result["queued"] == 1

    def test_skips_downloaded_videos(self, app, sample_video):
        """Should skip already downloaded videos."""
        with app.app_context():
            video = db.session.get(Video, sample_video)
            video.downloaded = True
            db.session.commit()

            result = schedule_downloads([sample_video])

            assert result["queued"] == 0

    def test_schedules_pending_videos(self, app, sample_video):
        """Should schedule pending videos when no IDs provided."""
        with app.app_context():
            result = schedule_downloads()

            assert result["queued"] == 1

    def test_respects_auto_download_setting(self, app, sample_list, sample_video):
        """Should skip videos from lists with auto_download disabled."""
        with app.app_context():
            video_list = db.session.get(VideoList, sample_list)
            video_list.auto_download = False
            db.session.commit()

            result = schedule_downloads()

            assert result["queued"] == 0


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
