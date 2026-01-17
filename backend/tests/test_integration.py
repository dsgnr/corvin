"""Integration tests for full workflows."""

from unittest.mock import MagicMock, patch


class TestListCreationToSyncFlow:
    """Integration tests for list creation -> sync -> download flow."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.YtDlpService.download_list_artwork")
    @patch("app.routes.lists.YtDlpService.write_channel_nfo")
    @patch("app.routes.lists.enqueue_task")
    def test_create_list_triggers_sync(
        self,
        mock_enqueue,
        mock_nfo,
        mock_artwork,
        mock_metadata,
        client,
        sample_profile,
    ):
        """Should create list, fetch metadata, and enqueue sync task."""
        mock_metadata.return_value = {
            "name": "Test Channel",
            "description": "A test channel",
            "thumbnail": "https://example.com/thumb.jpg",
            "thumbnails": [],
            "tags": ["tech"],
            "extractor": "Youtube",
        }
        mock_task = MagicMock()
        mock_task.to_dict.return_value = {"id": 1}
        mock_enqueue.return_value = mock_task

        response = client.post(
            "/api/lists",
            json={
                "name": "New Channel",
                "url": "https://youtube.com/c/newchannel",
                "profile_id": sample_profile,
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Channel"
        assert data["description"] == "A test channel"
        mock_enqueue.assert_called_once()  # Sync was triggered

    @patch("app.services.ytdlp_service.YtDlpService.extract_videos")
    @patch("app.services.history_service.HistoryService.log")
    def test_sync_discovers_videos(self, mock_history, mock_extract, app, sample_list):
        """Should discover and save new videos during sync."""
        from app.models import Video
        from app.tasks import sync_single_list

        # Mock extract_videos to call the callback with video data
        def mock_extract_impl(url, from_date, on_video_fetched, existing_ids):
            video_data = {
                "video_id": "new123",
                "title": "New Video",
                "description": "A new video",
                "url": "https://youtube.com/watch?v=new123",
                "duration": 600,
                "upload_date": None,
                "thumbnail": "https://example.com/thumb.jpg",
                "extractor": "Youtube",
                "media_type": "video",
                "labels": {},
            }
            if on_video_fetched:
                on_video_fetched(video_data)
            return [video_data]

        mock_extract.side_effect = mock_extract_impl

        with app.app_context():
            initial_count = Video.query.filter_by(list_id=sample_list).count()

            result = sync_single_list(app, sample_list)

            final_count = Video.query.filter_by(list_id=sample_list).count()
            assert final_count == initial_count + 1
            assert result["new_videos"] == 1

    @patch("app.services.ytdlp_service.YtDlpService.download_video")
    @patch("app.services.history_service.HistoryService.log")
    def test_download_marks_video_complete(
        self, mock_history, mock_download, app, sample_video
    ):
        """Should mark video as downloaded after successful download."""
        from app.extensions import db
        from app.models import Video
        from app.tasks import download_single_video

        mock_download.return_value = (True, "/downloads/test.mp4", {"format": "mp4"})

        with app.app_context():
            result = download_single_video(app, sample_video)

            video = db.session.get(Video, sample_video)
            assert video.downloaded is True
            assert video.download_path == "/downloads/test.mp4"
            assert result["status"] == "completed"


class TestTaskQueueFlow:
    """Integration tests for task queue operations."""

    def test_enqueue_and_retrieve_task(self, app, sample_list):
        """Should enqueue task and retrieve it via API."""
        from app.tasks import enqueue_task

        with app.app_context():
            task = enqueue_task("sync", sample_list)
            task_id = task.id

        # Now retrieve via API

        with app.test_client() as client:
            response = client.get(f"/api/tasks/{task_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["task_type"] == "sync"
            assert data["entity_id"] == sample_list
            assert data["status"] == "pending"

    def test_bulk_task_operations(self, client, app, sample_list):
        """Should handle bulk task pause/resume/cancel."""
        from app.extensions import db
        from app.models.task import Task, TaskStatus, TaskType

        # Create multiple tasks
        with app.app_context():
            for i in range(3):
                task = Task(
                    task_type=TaskType.SYNC.value,
                    entity_id=sample_list + i,
                    status=TaskStatus.PENDING.value,
                )
                db.session.add(task)
            db.session.commit()

        # Pause all
        response = client.post("/api/tasks/pause/all")
        assert response.status_code == 200
        assert response.get_json()["affected"] >= 3

        # Resume all
        response = client.post("/api/tasks/resume/all")
        assert response.status_code == 200

        # Cancel all
        response = client.post("/api/tasks/cancel/all")
        assert response.status_code == 200


class TestProfileListVideoRelationships:
    """Integration tests for profile -> list -> video relationships."""

    def test_delete_profile_blocked_by_lists(self, client, sample_profile, sample_list):
        """Should not delete profile with associated lists."""
        response = client.delete(f"/api/profiles/{sample_profile}")

        assert response.status_code == 409
        assert "associated list" in response.get_json()["error"].lower()

    def test_delete_list_cascades_to_videos(
        self, client, app, sample_list, sample_video
    ):
        """Should delete videos when list is deleted."""
        from app.extensions import db
        from app.models import Video

        # Verify video exists
        with app.app_context():
            assert db.session.get(Video, sample_video) is not None

        # Delete list
        response = client.delete(f"/api/lists/{sample_list}")
        assert response.status_code == 204

        # Verify video is gone
        with app.app_context():
            assert db.session.get(Video, sample_video) is None

    def test_profile_update_affects_list_downloads(
        self, client, app, sample_profile, sample_list
    ):
        """Should use updated profile settings for downloads."""
        # Update profile
        response = client.put(
            f"/api/profiles/{sample_profile}",
            json={"output_format": "mkv"},
        )
        assert response.status_code == 200

        # Verify profile was updated
        with app.app_context():
            from app.models import Profile

            profile = Profile.query.get(sample_profile)
            assert profile.output_format == "mkv"


class TestHistoryTracking:
    """Integration tests for history/audit logging."""

    @patch("app.routes.lists.YtDlpService.extract_list_metadata")
    @patch("app.routes.lists.enqueue_task")
    def test_list_creation_logged(
        self, mock_enqueue, mock_metadata, client, sample_profile
    ):
        """Should log list creation in history."""
        mock_metadata.return_value = {}
        mock_enqueue.return_value = None

        # Create list
        client.post(
            "/api/lists",
            json={
                "name": "History Test",
                "url": "https://youtube.com/c/historytest",
                "profile_id": sample_profile,
            },
        )

        # Check history
        response = client.get("/api/history?action=list_created")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 1
        assert any(e["details"].get("name") == "History Test" for e in data)

    def test_profile_crud_logged(self, client):
        """Should log profile create/update/delete in history."""
        # Create
        response = client.post("/api/profiles", json={"name": "CRUD Test"})
        profile_id = response.get_json()["id"]

        # Update
        client.put(f"/api/profiles/{profile_id}", json={"name": "CRUD Updated"})

        # Delete
        client.delete(f"/api/profiles/{profile_id}")

        # Check history
        response = client.get("/api/history?entity_type=profile")
        data = response.get_json()

        actions = [e["action"] for e in data]
        assert "profile_created" in actions
        assert "profile_updated" in actions
        assert "profile_deleted" in actions
