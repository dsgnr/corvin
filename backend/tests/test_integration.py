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
        data = response.json()
        assert data["name"] == "New Channel"
        assert data["description"] == "A test channel"
        mock_enqueue.assert_called_once()  # Sync was triggered


class TestTaskQueueFlow:
    """Integration tests for task queue operations."""

    def test_bulk_task_operations(self, client, db_session, sample_list):
        """Should handle bulk task pause/resume/cancel."""
        from app.models.task import Task, TaskStatus, TaskType

        # Create multiple tasks
        for i in range(3):
            task = Task(
                task_type=TaskType.SYNC.value,
                entity_id=sample_list + i,
                status=TaskStatus.PENDING.value,
            )
            db_session.add(task)
        db_session.commit()

        # Pause all
        response = client.post("/api/tasks/pause/all")
        assert response.status_code == 200
        assert response.json()["affected"] >= 3

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
        assert "associated list" in response.json()["error"].lower()

    @patch("app.routes.lists.threading.Thread")
    def test_delete_list_accepted(
        self, mock_thread, client, db_session, sample_list, sample_video
    ):
        """Should accept list deletion request (async)."""
        from app.models import Video

        # Verify video exists
        assert db_session.query(Video).get(sample_video) is not None

        # Delete list - returns 202 Accepted for async deletion
        response = client.delete(f"/api/lists/{sample_list}")
        assert response.status_code == 202
        assert "message" in response.json()
        # Verify background thread was started (but mocked to prevent DB access after teardown)
        mock_thread.assert_called_once()


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
        data = response.json()
        entries = data["entries"]
        assert len(entries) >= 1
        assert any(e["details"].get("name") == "History Test" for e in entries)

    def test_profile_crud_logged(self, client):
        """Should log profile create/update/delete in history."""
        # Create
        response = client.post("/api/profiles", json={"name": "CRUD Test"})
        profile_id = response.json()["id"]

        # Update
        client.put(f"/api/profiles/{profile_id}", json={"name": "CRUD Updated"})

        # Delete
        client.delete(f"/api/profiles/{profile_id}")

        # Check history
        response = client.get("/api/history?entity_type=profile")
        data = response.json()
        entries = data["entries"]

        actions = [e["action"] for e in entries]
        assert "profile_created" in actions
        assert "profile_updated" in actions
        assert "profile_deleted" in actions
