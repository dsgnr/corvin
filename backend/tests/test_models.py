"""Tests for database models."""

from datetime import datetime, timedelta

from app.models import Profile, Video, VideoList
from app.models.task import Task, TaskLogLevel, TaskStatus, TaskType


class TestVideoList:
    """Tests for VideoList model."""

    def test_is_due_for_sync_no_last_synced(self, db_session, sample_profile):
        """Should be due for sync if never synced."""
        video_list = VideoList(
            name="Test",
            url="https://example.com",
            profile_id=sample_profile,
        )
        db_session.add(video_list)
        db_session.commit()

        assert video_list.is_due_for_sync() is True

    def test_is_due_for_sync_daily(self, db_session, sample_profile):
        """Should be due after 1 day for daily frequency."""
        video_list = VideoList(
            name="Test",
            url="https://example.com",
            profile_id=sample_profile,
            sync_frequency="daily",
            last_synced=datetime.utcnow() - timedelta(days=2),
        )
        db_session.add(video_list)
        db_session.commit()

        assert video_list.is_due_for_sync() is True

    def test_is_not_due_for_sync_daily(self, db_session, sample_profile):
        """Should not be due within 1 day for daily frequency."""
        video_list = VideoList(
            name="Test",
            url="https://example.com",
            profile_id=sample_profile,
            sync_frequency="daily",
            last_synced=datetime.utcnow() - timedelta(hours=12),
        )
        db_session.add(video_list)
        db_session.commit()

        assert video_list.is_due_for_sync() is False

    def test_to_dict(self, db_session, sample_profile):
        """Should serialise to dictionary."""
        video_list = VideoList(
            name="Test Channel",
            url="https://example.com",
            profile_id=sample_profile,
            tags="tech,coding",
        )
        db_session.add(video_list)
        db_session.commit()

        result = video_list.to_dict()

        assert result["name"] == "Test Channel"
        assert result["tags"] == ["tech", "coding"]


class TestProfile:
    """Tests for Profile model."""

    def test_to_dict_includes_include_live(self, db_session):
        """Should include include_live in to_dict output."""
        profile = Profile(name="Test", include_live=False)
        db_session.add(profile)
        db_session.commit()

        result = profile.to_dict()

        assert "include_live" in result
        assert result["include_live"] is False

    def test_include_live_defaults_to_true(self, db_session):
        """Should default include_live to True."""
        profile = Profile(name="Default Test")
        db_session.add(profile)
        db_session.commit()

        assert profile.include_live is True

    def test_to_yt_dlp_opts_basic(self, db_session):
        """Should generate basic yt-dlp options."""
        profile = Profile(name="Test")
        db_session.add(profile)
        db_session.commit()

        opts = profile.to_yt_dlp_opts()

        assert "postprocessors" in opts
        assert opts["merge_output_format"] == "mp4"
        assert opts["format"] == "bv*+ba[acodec=opus]/bv*+ba/best"

    def test_to_yt_dlp_opts_with_subtitles(self, db_session):
        """Should include subtitle options when enabled."""
        profile = Profile(
            name="Subtitles",
            download_subtitles=True,
            subtitle_languages="en,es",
        )
        db_session.add(profile)
        db_session.commit()

        opts = profile.to_yt_dlp_opts()

        assert opts["writesubtitles"] is True
        assert opts["subtitleslangs"] == ["en", "es"]

    def test_to_yt_dlp_opts_with_sponsorblock(self, db_session):
        """Should include sponsorblock options when enabled."""
        profile = Profile(
            name="Sponsorblock",
            sponsorblock_behaviour="delete",
            sponsorblock_categories="sponsor,intro",
        )
        db_session.add(profile)
        db_session.commit()

        opts = profile.to_yt_dlp_opts()

        pp_keys = [pp["key"] for pp in opts["postprocessors"]]
        assert "SponsorBlock" in pp_keys


class TestTask:
    """Tests for Task model."""

    def test_add_log(self, db_session, sample_list):
        """Should add log entry to task."""
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.PENDING.value,
        )
        db_session.add(task)
        db_session.commit()

        task.add_log(db_session, "Test message", TaskLogLevel.INFO.value, attempt=1)
        db_session.commit()

        assert task.logs.count() == 1
        assert task.logs.first().message == "Test message"

    def test_to_dict_with_logs(self, db_session, sample_list):
        """Should include logs when requested."""
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.PENDING.value,
        )
        db_session.add(task)
        db_session.commit()

        task.add_log(db_session, "Log entry")
        db_session.commit()

        result = task.to_dict(include_logs=True)

        assert "logs" in result
        assert len(result["logs"]) == 1


class TestVideo:
    """Tests for Video model."""

    def test_to_dict(self, db_session, sample_video):
        """Should serialise to dictionary."""
        video = db_session.query(Video).get(sample_video)

        result = video.to_dict()

        assert result["title"] == "Test Video"
        assert result["downloaded"] is False
        assert result["labels"] == {}
        assert "created_at" in result

    def test_to_dict_with_labels(self, db_session, sample_list):
        """Should include labels in dictionary."""
        video = Video(
            video_id="test456",
            title="Video with Labels",
            url="https://example.com/video",
            list_id=sample_list,
            labels={
                "acodec": "opus",
                "resolution": "2160p",
            },
        )
        db_session.add(video)
        db_session.commit()

        result = video.to_dict()

        assert result["labels"]["acodec"] == "opus"
        assert result["labels"]["resolution"] == "2160p"


class TestVideoListGetVideoStats:
    """Tests for VideoList.get_video_stats method."""

    def test_get_video_stats_with_videos(self, db_session, sample_list, sample_video):
        """Should return correct counts."""
        video_list = db_session.query(VideoList).get(sample_list)
        stats = video_list.get_video_stats(db_session)

        assert stats["total"] == 1
        assert stats["downloaded"] == 0
        assert stats["pending"] == 1

    def test_handles_no_videos(self, db_session, sample_profile):
        """Should return zeros when no videos."""
        video_list = VideoList(
            name="Empty",
            url="https://youtube.com/c/empty",
            profile_id=sample_profile,
        )
        db_session.add(video_list)
        db_session.commit()

        stats = video_list.get_video_stats(db_session)

        assert stats["total"] == 0
        assert stats["downloaded"] == 0
        assert stats["failed"] == 0
        assert stats["pending"] == 0

    def test_counts_failed_correctly(self, db_session, sample_list):
        """Should count failed videos correctly."""
        # Add a failed video
        video = Video(
            video_id="failed123",
            title="Failed Video",
            url="https://youtube.com/watch?v=failed123",
            list_id=sample_list,
            downloaded=False,
            error_message="Download failed",
        )
        db_session.add(video)
        db_session.commit()

        video_list = db_session.query(VideoList).get(sample_list)
        stats = video_list.get_video_stats(db_session)

        # sample_list already has sample_video, so total is 2
        assert stats["failed"] >= 1

    def test_pending_calculation(self, db_session, sample_profile):
        """Test pending = total - downloaded - failed calculation."""
        # Create a fresh list without sample_video
        video_list = VideoList(
            name="Stats Test",
            url="https://youtube.com/c/statstest",
            profile_id=sample_profile,
        )
        db_session.add(video_list)
        db_session.commit()

        # Add various videos
        videos = [
            Video(
                video_id="pending1",
                title="Pending 1",
                url="https://youtube.com/watch?v=pending1",
                list_id=video_list.id,
                downloaded=False,
            ),
            Video(
                video_id="pending2",
                title="Pending 2",
                url="https://youtube.com/watch?v=pending2",
                list_id=video_list.id,
                downloaded=False,
            ),
            Video(
                video_id="downloaded1",
                title="Downloaded 1",
                url="https://youtube.com/watch?v=downloaded1",
                list_id=video_list.id,
                downloaded=True,
            ),
            Video(
                video_id="failed1",
                title="Failed 1",
                url="https://youtube.com/watch?v=failed1",
                list_id=video_list.id,
                downloaded=False,
                error_message="Error",
            ),
        ]
        db_session.add_all(videos)
        db_session.commit()

        stats = video_list.get_video_stats(db_session)

        assert stats["total"] == 4
        assert stats["downloaded"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 2  # 4 - 1 - 1 = 2


class TestTaskBatchGetEntityNames:
    """Tests for Task.batch_get_entity_names static method."""

    def test_batch_get_entity_names_empty(self, db_session):
        """Should return empty dict for empty list."""
        result = Task.batch_get_entity_names(db_session, [])
        assert result == {}

    def test_batch_get_entity_names_sync_tasks(self, db_session, sample_list):
        """Should fetch list names for sync tasks."""
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status="pending",
        )
        db_session.add(task)
        db_session.commit()

        result = Task.batch_get_entity_names(db_session, [task])
        assert task.id in result
        assert result[task.id] == "Test Channel"

    def test_batch_get_entity_names_download_tasks(self, db_session, sample_video):
        """Should fetch video titles for download tasks."""
        task = Task(
            task_type=TaskType.DOWNLOAD.value,
            entity_id=sample_video,
            status="pending",
        )
        db_session.add(task)
        db_session.commit()

        result = Task.batch_get_entity_names(db_session, [task])
        assert task.id in result
        assert result[task.id] == "Test Video"
