"""Tests for task API endpoints."""

from unittest.mock import patch

from app.extensions import db
from app.models.task import Task, TaskStatus


class TestListTasks:
    """Tests for GET /api/tasks."""

    def test_list_tasks_empty(self, client):
        """Should return empty list when no tasks exist."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_tasks_with_data(self, client, sample_task):
        """Should return all tasks."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_tasks_filter_by_type(self, client, sample_task):
        """Should filter tasks by type."""
        response = client.get("/api/tasks?type=sync")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_tasks_filter_by_status(self, client, sample_task):
        """Should filter tasks by status."""
        response = client.get("/api/tasks?status=pending")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_list_tasks_pagination(self, client, sample_task):
        """Should support limit and offset."""
        response = client.get("/api/tasks?limit=10&offset=0")

        assert response.status_code == 200


class TestGetTask:
    """Tests for GET /api/tasks/<id>."""

    def test_get_task_success(self, client, sample_task):
        """Should return task by ID."""
        response = client.get(f"/api/tasks/{sample_task}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == sample_task

    def test_get_task_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.get("/api/tasks/9999")

        assert response.status_code == 404

    def test_get_task_without_logs(self, client, sample_task):
        """Should exclude logs when requested."""
        response = client.get(f"/api/tasks/{sample_task}?include_logs=false")

        assert response.status_code == 200
        data = response.get_json()
        assert "logs" not in data


class TestGetTaskLogs:
    """Tests for GET /api/tasks/<id>/logs."""

    def test_get_task_logs_empty(self, client, sample_task):
        """Should return empty logs for task without logs."""
        response = client.get(f"/api/tasks/{sample_task}/logs")

        assert response.status_code == 200
        assert response.get_json() == []

    def test_get_task_logs_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.get("/api/tasks/9999/logs")

        assert response.status_code == 404


class TestTaskStats:
    """Tests for GET /api/tasks/stats."""

    def test_get_stats(self, client):
        """Should return task statistics."""
        response = client.get("/api/tasks/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert "pending_sync" in data
        assert "pending_download" in data


class TestTriggerListSync:
    """Tests for POST /api/tasks/sync/list/<id>."""

    @patch("app.routes.tasks.enqueue_task")
    def test_trigger_sync_success(self, mock_enqueue, client, sample_list):
        """Should trigger sync for a list."""
        mock_task = {
            "id": 1,
            "task_type": "sync",
            "entity_id": sample_list,
            "status": "pending",
        }
        mock_enqueue.return_value = type("Task", (), {"to_dict": lambda s: mock_task})()

        response = client.post(f"/api/tasks/sync/list/{sample_list}")

        assert response.status_code == 202

    @patch("app.routes.tasks.enqueue_task")
    def test_trigger_sync_already_queued(self, mock_enqueue, client, sample_list):
        """Should return conflict when sync already queued."""
        mock_enqueue.return_value = None

        response = client.post(f"/api/tasks/sync/list/{sample_list}")

        assert response.status_code == 409


class TestTriggerListsSync:
    """Tests for POST /api/tasks/sync/lists."""

    @patch("app.routes.tasks.schedule_syncs")
    def test_trigger_lists_sync_success(self, mock_schedule, client, sample_list):
        """Should trigger sync for multiple lists."""
        mock_schedule.return_value = {"queued": 1, "skipped": 0}

        response = client.post(
            "/api/tasks/sync/lists",
            json={"list_ids": [sample_list]},
        )

        assert response.status_code == 202
        data = response.get_json()
        assert data["queued"] == 1

    def test_trigger_lists_sync_missing_ids(self, client):
        """Should reject request without list_ids."""
        response = client.post("/api/tasks/sync/lists", json={})

        assert response.status_code == 400

    def test_trigger_lists_sync_invalid_ids(self, client):
        """Should reject non-array list_ids."""
        response = client.post(
            "/api/tasks/sync/lists",
            json={"list_ids": "invalid"},
        )

        assert response.status_code == 400


class TestTriggerAllSyncs:
    """Tests for POST /api/tasks/sync/all."""

    @patch("app.routes.tasks.schedule_syncs")
    def test_trigger_all_syncs(self, mock_schedule, client):
        """Should trigger sync for all enabled lists."""
        mock_schedule.return_value = {"queued": 2, "skipped": 0}

        response = client.post("/api/tasks/sync/all")

        assert response.status_code == 202


class TestTriggerVideoDownload:
    """Tests for POST /api/tasks/download/video/<id>."""

    @patch("app.routes.tasks.enqueue_task")
    def test_trigger_download_success(self, mock_enqueue, client, sample_video):
        """Should trigger download for a video."""
        mock_task = {
            "id": 1,
            "task_type": "download",
            "entity_id": sample_video,
            "status": "pending",
        }
        mock_enqueue.return_value = type("Task", (), {"to_dict": lambda s: mock_task})()

        response = client.post(f"/api/tasks/download/video/{sample_video}")

        assert response.status_code == 202

    @patch("app.routes.tasks.enqueue_task")
    def test_trigger_download_already_queued(self, mock_enqueue, client, sample_video):
        """Should return conflict when download already queued."""
        mock_enqueue.return_value = None

        response = client.post(f"/api/tasks/download/video/{sample_video}")

        assert response.status_code == 409


class TestTriggerVideosDownload:
    """Tests for POST /api/tasks/download/videos."""

    @patch("app.routes.tasks.schedule_downloads")
    def test_trigger_videos_download_success(self, mock_schedule, client, sample_video):
        """Should trigger download for multiple videos."""
        mock_schedule.return_value = {"queued": 1, "skipped": 0}

        response = client.post(
            "/api/tasks/download/videos",
            json={"video_ids": [sample_video]},
        )

        assert response.status_code == 202

    def test_trigger_videos_download_missing_ids(self, client):
        """Should reject request without video_ids."""
        response = client.post("/api/tasks/download/videos", json={})

        assert response.status_code == 400


class TestTriggerPendingDownloads:
    """Tests for POST /api/tasks/download/pending."""

    @patch("app.routes.tasks.schedule_downloads")
    def test_trigger_pending_downloads(self, mock_schedule, client):
        """Should trigger download for all pending videos."""
        mock_schedule.return_value = {"queued": 5, "skipped": 0}

        response = client.post("/api/tasks/download/pending")

        assert response.status_code == 202


class TestRetryTask:
    """Tests for POST /api/tasks/<id>/retry."""

    def test_retry_failed_task(self, client, app, sample_task):
        """Should retry a failed task."""
        with app.app_context():
            task = db.session.get(Task, sample_task)
            task.status = TaskStatus.FAILED.value
            db.session.commit()

        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_retry_completed_task(self, client, app, sample_task):
        """Should retry a completed task."""
        with app.app_context():
            task = db.session.get(Task, sample_task)
            task.status = TaskStatus.COMPLETED.value
            db.session.commit()

        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 200

    def test_retry_task_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.post("/api/tasks/9999/retry")

        assert response.status_code == 404

    def test_retry_pending_task(self, client, sample_task):
        """Should reject retry for pending task."""
        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 400
