"""Tests for database models."""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Profile, Video, VideoList
from app.models.task import Task, TaskLogLevel, TaskStatus, TaskType


class TestVideoList:
    """Tests for VideoList model."""

    def test_is_due_for_sync_no_last_synced(self, app, sample_profile):
        """Should be due for sync if never synced."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_is_due_for_sync_daily(self, app, sample_profile):
        """Should be due after 1 day for daily frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
                sync_frequency="daily",
                last_synced=datetime.utcnow() - timedelta(days=2),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_is_not_due_for_sync_daily(self, app, sample_profile):
        """Should not be due within 1 day for daily frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
                sync_frequency="daily",
                last_synced=datetime.utcnow() - timedelta(hours=12),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is False

    def test_is_due_for_sync_weekly(self, app, sample_profile):
        """Should be due after 1 week for weekly frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
                sync_frequency="weekly",
                last_synced=datetime.utcnow() - timedelta(weeks=2),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_to_dict(self, app, sample_profile):
        """Should serialise to dictionary."""
        with app.app_context():
            video_list = VideoList(
                name="Test Channel",
                url="https://example.com",
                profile_id=sample_profile,
                tags="tech,coding",
            )
            db.session.add(video_list)
            db.session.commit()

            result = video_list.to_dict()

            assert result["name"] == "Test Channel"
            assert result["tags"] == ["tech", "coding"]

    def test_to_dict_with_videos(self, app, sample_list, sample_video):
        """Should include videos when requested."""
        with app.app_context():
            video_list = db.session.get(VideoList, sample_list)

            result = video_list.to_dict(include_videos=True)

            assert "videos" in result
            assert len(result["videos"]) == 1


class TestProfile:
    """Tests for Profile model."""

    def test_to_yt_dlp_opts_basic(self, app):
        """Should generate basic yt-dlp options."""
        with app.app_context():
            profile = Profile(name="Test")
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            assert "postprocessors" in opts
            assert opts["final_ext"] == "mp4"

    def test_to_yt_dlp_opts_with_subtitles(self, app):
        """Should include subtitle options when enabled."""
        with app.app_context():
            profile = Profile(
                name="Subtitles",
                download_subtitles=True,
                subtitle_languages="en,es",
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            assert opts["writesubtitles"] is True
            assert opts["subtitleslangs"] == ["en", "es"]

    def test_to_yt_dlp_opts_with_sponsorblock(self, app):
        """Should include sponsorblock options when enabled."""
        with app.app_context():
            profile = Profile(
                name="Sponsorblock",
                sponsorblock_behavior="delete",
                sponsorblock_categories="sponsor,intro",
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            # Check sponsorblock postprocessor exists
            pp_keys = [pp["key"] for pp in opts["postprocessors"]]
            assert "SponsorBlock" in pp_keys


class TestTask:
    """Tests for Task model."""

    def test_add_log(self, app, sample_list):
        """Should add log entry to task."""
        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list,
                status=TaskStatus.PENDING.value,
            )
            db.session.add(task)
            db.session.commit()

            task.add_log("Test message", TaskLogLevel.INFO.value, attempt=1)
            db.session.commit()

            assert task.logs.count() == 1
            assert task.logs.first().message == "Test message"

    def test_to_dict_includes_entity_name(self, app, sample_list):
        """Should include entity name in dict."""
        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list,
                status=TaskStatus.PENDING.value,
            )
            db.session.add(task)
            db.session.commit()

            result = task.to_dict()

            assert result["entity_name"] == "Test Channel"

    def test_to_dict_with_logs(self, app, sample_list):
        """Should include logs when requested."""
        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list,
                status=TaskStatus.PENDING.value,
            )
            db.session.add(task)
            db.session.commit()

            task.add_log("Log entry")
            db.session.commit()

            result = task.to_dict(include_logs=True)

            assert "logs" in result
            assert len(result["logs"]) == 1


class TestVideo:
    """Tests for Video model."""

    def test_to_dict(self, app, sample_video):
        """Should serialise to dictionary."""
        with app.app_context():
            video = db.session.get(Video, sample_video)

            result = video.to_dict()

            assert result["title"] == "Test Video"
            assert result["downloaded"] is False
            assert result["labels"] == {}  # Default empty dict when None
            assert "created_at" in result

    def test_to_dict_with_labels(self, app, sample_list):
        """Should include labels in dictionary."""
        with app.app_context():
            video = Video(
                video_id="test456",
                title="Video with Labels",
                url="https://example.com/video",
                list_id=sample_list,
                labels={
                    "acodec": "opus",
                    "resolution": "2160p",
                    "audio_channels": 2,
                    "dynamic_range": "HDR",
                    "filesize_approx": 1073741824,
                },
            )
            db.session.add(video)
            db.session.commit()

            result = video.to_dict()

            assert result["labels"]["acodec"] == "opus"
            assert result["labels"]["resolution"] == "2160p"
            assert result["labels"]["audio_channels"] == 2
            assert result["labels"]["dynamic_range"] == "HDR"
            assert result["labels"]["filesize_approx"] == 1073741824
