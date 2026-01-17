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


class TestVideoListNextSyncAt:
    """Tests for VideoList.next_sync_at method."""

    def test_next_sync_at_returns_none_when_never_synced(self, app, sample_profile):
        """Should return None if never synced."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.next_sync_at() is None

    def test_next_sync_at_calculates_correctly(self, app, sample_profile):
        """Should calculate next sync time based on frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Test",
                url="https://example.com",
                profile_id=sample_profile,
                sync_frequency="daily",
                last_synced=datetime.utcnow(),
            )
            db.session.add(video_list)
            db.session.commit()

            next_sync = video_list.next_sync_at()
            assert next_sync is not None
            assert next_sync > datetime.utcnow()


class TestVideoListGetVideoStats:
    """Tests for VideoList.get_video_stats method."""

    def test_get_video_stats_empty(self, app, sample_list):
        """Should return zeros when no videos."""
        with app.app_context():
            # Delete the sample video first
            Video.query.filter_by(list_id=sample_list).delete()
            db.session.commit()

            video_list = db.session.get(VideoList, sample_list)
            stats = video_list.get_video_stats()

            assert stats["total"] == 0
            assert stats["downloaded"] == 0
            assert stats["failed"] == 0
            assert stats["pending"] == 0

    def test_get_video_stats_with_videos(self, app, sample_list, sample_video):
        """Should return correct counts."""
        with app.app_context():
            video_list = db.session.get(VideoList, sample_list)
            stats = video_list.get_video_stats()

            assert stats["total"] == 1
            assert stats["downloaded"] == 0
            assert stats["pending"] == 1


class TestTaskBatchGetEntityNames:
    """Tests for Task.batch_get_entity_names static method."""

    def test_batch_get_entity_names_empty(self, app):
        """Should return empty dict for empty list."""
        with app.app_context():
            result = Task.batch_get_entity_names([])
            assert result == {}

    def test_batch_get_entity_names_sync_tasks(self, app, sample_list):
        """Should fetch list names for sync tasks."""
        from app.models.task import TaskType

        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            result = Task.batch_get_entity_names([task])
            assert task.id in result
            assert result[task.id] == "Test Channel"

    def test_batch_get_entity_names_download_tasks(self, app, sample_video):
        """Should fetch video titles for download tasks."""
        from app.models.task import TaskType

        with app.app_context():
            task = Task(
                task_type=TaskType.DOWNLOAD.value,
                entity_id=sample_video,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            result = Task.batch_get_entity_names([task])
            assert task.id in result
            assert result[task.id] == "Test Video"


class TestHistoryToDict:
    """Tests for History.to_dict method."""

    def test_to_dict(self, app):
        """Should serialise history entry to dict."""
        from app.models import History, HistoryAction

        with app.app_context():
            entry = History(
                action=HistoryAction.PROFILE_CREATED.value,
                entity_type="profile",
                entity_id=1,
                details={"name": "Test"},
            )
            db.session.add(entry)
            db.session.commit()

            result = entry.to_dict()

            assert result["id"] == entry.id
            assert result["action"] == "profile_created"
            assert result["entity_type"] == "profile"
            assert result["entity_id"] == 1
            assert result["details"] == {"name": "Test"}
            assert "created_at" in result

    def test_to_dict_with_none_details(self, app):
        """Should handle None details."""
        from app.models import History, HistoryAction

        with app.app_context():
            entry = History(
                action=HistoryAction.PROFILE_DELETED.value,
                entity_type="profile",
                entity_id=1,
                details=None,
            )
            db.session.add(entry)
            db.session.commit()

            result = entry.to_dict()
            assert result["details"] == {}


class TestProfileToYtDlpOptsEdgeCases:
    """Additional tests for Profile.to_yt_dlp_opts edge cases."""

    def test_to_yt_dlp_opts_with_auto_generated_subtitles(self, app):
        """Should include auto-generated subtitle options."""
        with app.app_context():
            profile = Profile(
                name="AutoSubs",
                auto_generated_subtitles=True,
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            assert opts["writeautomaticsub"] is True

    def test_to_yt_dlp_opts_with_embed_subtitles(self, app):
        """Should include embed subtitle postprocessor."""
        with app.app_context():
            profile = Profile(
                name="EmbedSubs",
                embed_subtitles=True,
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            pp_keys = [pp["key"] for pp in opts["postprocessors"]]
            assert "FFmpegEmbedSubtitle" in pp_keys

    def test_to_yt_dlp_opts_with_mark_chapter_sponsorblock(self, app):
        """Should include chapter marking for sponsorblock."""
        with app.app_context():
            profile = Profile(
                name="MarkChapter",
                sponsorblock_behavior="mark_chapter",
                sponsorblock_categories="sponsor",
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            pp_keys = [pp["key"] for pp in opts["postprocessors"]]
            assert "SponsorBlock" in pp_keys
            assert "ModifyChapters" in pp_keys

    def test_to_yt_dlp_opts_invalid_output_format(self, app):
        """Should fallback to mp4 for invalid output format."""
        with app.app_context():
            profile = Profile(
                name="InvalidFormat",
                output_format="invalid",
            )
            db.session.add(profile)
            db.session.commit()

            opts = profile.to_yt_dlp_opts()

            assert opts["final_ext"] == "mp4"


class TestTaskLogToDict:
    """Tests for TaskLog.to_dict method."""

    def test_to_dict(self, app, sample_list):
        """Should serialise task log to dict."""
        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list,
                status=TaskStatus.PENDING.value,
            )
            db.session.add(task)
            db.session.commit()

            log = task.add_log("Test message", TaskLogLevel.WARNING.value, attempt=2)
            db.session.commit()

            result = log.to_dict()

            assert result["attempt"] == 2
            assert result["level"] == "warning"
            assert result["message"] == "Test message"
            assert "created_at" in result


class TestVideoListSyncFrequencies:
    """Tests for VideoList with different sync frequencies."""

    def test_is_due_for_sync_hourly(self, app, sample_profile):
        """Should be due after 1 hour for hourly frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Hourly",
                url="https://example.com/hourly",
                profile_id=sample_profile,
                sync_frequency="hourly",
                last_synced=datetime.utcnow() - timedelta(hours=2),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_is_not_due_for_sync_hourly(self, app, sample_profile):
        """Should not be due within 1 hour for hourly frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Hourly",
                url="https://example.com/hourly2",
                profile_id=sample_profile,
                sync_frequency="hourly",
                last_synced=datetime.utcnow() - timedelta(minutes=30),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is False

    def test_is_due_for_sync_6h(self, app, sample_profile):
        """Should be due after 6 hours for 6h frequency."""
        with app.app_context():
            video_list = VideoList(
                name="6h",
                url="https://example.com/6h",
                profile_id=sample_profile,
                sync_frequency="6h",
                last_synced=datetime.utcnow() - timedelta(hours=7),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_is_due_for_sync_monthly(self, app, sample_profile):
        """Should be due after 30 days for monthly frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Monthly",
                url="https://example.com/monthly",
                profile_id=sample_profile,
                sync_frequency="monthly",
                last_synced=datetime.utcnow() - timedelta(days=31),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True

    def test_unknown_frequency_defaults_to_daily(self, app, sample_profile):
        """Should default to 24 hours for unknown frequency."""
        with app.app_context():
            video_list = VideoList(
                name="Unknown",
                url="https://example.com/unknown",
                profile_id=sample_profile,
                sync_frequency="unknown",
                last_synced=datetime.utcnow() - timedelta(hours=25),
            )
            db.session.add(video_list)
            db.session.commit()

            assert video_list.is_due_for_sync() is True


class TestProfileToDict:
    """Tests for Profile.to_dict method."""

    def test_to_dict_includes_all_fields(self, app):
        """Should include all profile fields in dict."""
        with app.app_context():
            profile = Profile(
                name="Full Profile",
                embed_metadata=False,
                embed_thumbnail=False,
                include_shorts=False,
                download_subtitles=True,
                embed_subtitles=True,
                auto_generated_subtitles=True,
                subtitle_languages="en,es,fr",
                audio_track_language="ja",
                sponsorblock_behavior="delete",
                sponsorblock_categories="sponsor,intro",
                output_format="mkv",
                extra_args='{"key": "value"}',
            )
            db.session.add(profile)
            db.session.commit()

            result = profile.to_dict()

            assert result["name"] == "Full Profile"
            assert result["embed_metadata"] is False
            assert result["embed_thumbnail"] is False
            assert result["include_shorts"] is False
            assert result["download_subtitles"] is True
            assert result["embed_subtitles"] is True
            assert result["auto_generated_subtitles"] is True
            assert result["subtitle_languages"] == "en,es,fr"
            assert result["audio_track_language"] == "ja"
            assert result["sponsorblock_behavior"] == "delete"
            assert result["sponsorblock_categories"] == "sponsor,intro"
            assert result["output_format"] == "mkv"
            assert "created_at" in result
            assert "updated_at" in result


class TestVideoWithError:
    """Tests for Video model with error states."""

    def test_to_dict_with_error_message(self, app, sample_list):
        """Should include error_message in dict."""
        with app.app_context():
            video = Video(
                video_id="error123",
                title="Failed Video",
                url="https://example.com/error",
                list_id=sample_list,
                error_message="Download failed: 403 Forbidden",
                retry_count=2,
            )
            db.session.add(video)
            db.session.commit()

            result = video.to_dict()

            assert result["error_message"] == "Download failed: 403 Forbidden"
            assert result["retry_count"] == 2
            assert result["downloaded"] is False

    def test_to_dict_with_download_path(self, app, sample_list):
        """Should include download_path when downloaded."""
        with app.app_context():
            video = Video(
                video_id="downloaded123",
                title="Downloaded Video",
                url="https://example.com/downloaded",
                list_id=sample_list,
                downloaded=True,
                download_path="/downloads/video.mp4",
            )
            db.session.add(video)
            db.session.commit()

            result = video.to_dict()

            assert result["downloaded"] is True
            assert result["download_path"] == "/downloads/video.mp4"


class TestTaskRetryCancelled:
    """Tests for Task retry with cancelled status."""

    def test_retry_cancelled_task_via_api(self, client, app, sample_task):
        """Should allow retry of cancelled task."""
        from app.models.task import TaskStatus

        with app.app_context():
            task = db.session.get(Task, sample_task)
            task.status = TaskStatus.CANCELLED.value
            db.session.commit()

        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"


class TestTaskGetEntityNameEdgeCases:
    """Tests for Task._get_entity_name edge cases."""

    def test_get_entity_name_unknown_type(self, app, sample_list):
        """Should return None for unknown task type."""
        with app.app_context():
            task = Task(
                task_type="unknown",
                entity_id=sample_list,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            result = task._get_entity_name()
            assert result is None

    def test_get_entity_name_missing_entity(self, app):
        """Should return None when entity doesn't exist."""
        with app.app_context():
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=99999,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            result = task._get_entity_name()
            assert result is None
