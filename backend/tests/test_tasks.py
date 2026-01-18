"""Tests for task API endpoints."""

from unittest.mock import patch

from app.models.task import Task, TaskStatus


class TestListTasks:
    """Tests for GET /api/tasks."""

    def test_list_tasks_empty(self, client):
        """Should return empty paginated response when no tasks exist."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_list_tasks_with_data(self, client, sample_task):
        """Should return all tasks in paginated response."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["total"] == 1

    def test_list_tasks_filter_by_type(self, client, sample_task):
        """Should filter tasks by type."""
        response = client.get("/api/tasks?type=sync")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1

    def test_list_tasks_filter_by_status(self, client, sample_task):
        """Should filter tasks by status."""
        response = client.get("/api/tasks?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1

    def test_list_tasks_filter_by_active_status(self, client, sample_task):
        """Should filter tasks by active status (pending or running)."""
        response = client.get("/api/tasks?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1

    def test_list_tasks_pagination(self, client, sample_task):
        """Should support pagination."""
        response = client.get("/api/tasks?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data


class TestTaskStats:
    """Tests for GET /api/tasks/stats."""

    def test_get_stats(self, client):
        """Should return task statistics."""
        response = client.get("/api/tasks/stats")

        assert response.status_code == 200
        data = response.json()
        assert "pending_sync" in data
        assert "pending_download" in data
        assert "running_sync" in data
        assert "running_download" in data


class TestTriggerListSync:
    """Tests for POST /api/tasks/sync/list/{list_id}."""

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


class TestTriggerAllSyncs:
    """Tests for POST /api/tasks/sync/all."""

    @patch("app.routes.tasks.schedule_syncs")
    def test_trigger_all_syncs(self, mock_schedule, client):
        """Should trigger sync for all enabled lists."""
        mock_schedule.return_value = {"queued": 2, "skipped": 0}

        response = client.post("/api/tasks/sync/all")

        assert response.status_code == 202
        data = response.json()
        assert data["queued"] == 2


class TestTriggerVideoDownload:
    """Tests for POST /api/tasks/download/video/{video_id}."""

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


class TestTriggerPendingDownloads:
    """Tests for POST /api/tasks/download/pending."""

    @patch("app.routes.tasks.schedule_downloads")
    def test_trigger_pending_downloads(self, mock_schedule, client):
        """Should trigger download for all pending videos."""
        mock_schedule.return_value = {"queued": 5, "skipped": 0}

        response = client.post("/api/tasks/download/pending")

        assert response.status_code == 202
        data = response.json()
        assert data["queued"] == 5


class TestRetryTask:
    """Tests for POST /api/tasks/{task_id}/retry."""

    def test_retry_failed_task(self, client, db_session, sample_task):
        """Should retry a failed task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.FAILED.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_retry_completed_task(self, client, db_session, sample_task):
        """Should retry a completed task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.COMPLETED.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/retry")

        assert response.status_code == 200

    def test_retry_cancelled_task(self, client, db_session, sample_task):
        """Should retry a cancelled task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.CANCELLED.value
        db_session.commit()

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


class TestPauseTask:
    """Tests for POST /api/tasks/{task_id}/pause."""

    def test_pause_pending_task(self, client, sample_task):
        """Should pause a pending task."""
        response = client.post(f"/api/tasks/{sample_task}/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    def test_pause_task_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.post("/api/tasks/9999/pause")

        assert response.status_code == 404

    def test_pause_non_pending_task(self, client, db_session, sample_task):
        """Should reject pause for non-pending task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.RUNNING.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/pause")

        assert response.status_code == 400


class TestResumeTask:
    """Tests for POST /api/tasks/{task_id}/resume."""

    def test_resume_paused_task(self, client, db_session, sample_task):
        """Should resume a paused task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.PAUSED.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_resume_task_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.post("/api/tasks/9999/resume")

        assert response.status_code == 404

    def test_resume_non_paused_task(self, client, sample_task):
        """Should reject resume for non-paused task."""
        response = client.post(f"/api/tasks/{sample_task}/resume")

        assert response.status_code == 400


class TestCancelTask:
    """Tests for POST /api/tasks/{task_id}/cancel."""

    def test_cancel_pending_task(self, client, sample_task):
        """Should cancel a pending task."""
        response = client.post(f"/api/tasks/{sample_task}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_paused_task(self, client, db_session, sample_task):
        """Should cancel a paused task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.PAUSED.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_task_not_found(self, client):
        """Should return 404 for non-existent task."""
        response = client.post("/api/tasks/9999/cancel")

        assert response.status_code == 404

    def test_cancel_running_task(self, client, db_session, sample_task):
        """Should reject cancel for running task."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.RUNNING.value
        db_session.commit()

        response = client.post(f"/api/tasks/{sample_task}/cancel")

        assert response.status_code == 400


class TestPauseAllTasks:
    """Tests for POST /api/tasks/pause/all."""

    def test_pause_all_pending_tasks(self, client, sample_task):
        """Should pause all pending tasks."""
        response = client.post("/api/tasks/pause/all")

        assert response.status_code == 200
        data = response.json()
        assert "affected" in data


class TestResumeAllTasks:
    """Tests for POST /api/tasks/resume/all."""

    def test_resume_all_paused_tasks(self, client, db_session, sample_task):
        """Should resume all paused tasks."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.PAUSED.value
        db_session.commit()

        response = client.post("/api/tasks/resume/all")

        assert response.status_code == 200
        data = response.json()
        assert data["affected"] == 1


class TestCancelAllTasks:
    """Tests for POST /api/tasks/cancel/all."""

    def test_cancel_all_tasks(self, client, sample_task):
        """Should cancel all pending/paused tasks."""
        response = client.post("/api/tasks/cancel/all")

        assert response.status_code == 200
        data = response.json()
        assert "affected" in data


class TestRetryFailedTasks:
    """Tests for POST /api/tasks/retry/failed."""

    def test_retry_all_failed_tasks(self, client, db_session, sample_task):
        """Should retry all failed tasks."""
        task = db_session.query(Task).get(sample_task)
        task.status = TaskStatus.FAILED.value
        db_session.commit()

        response = client.post("/api/tasks/retry/failed")

        assert response.status_code == 200
        data = response.json()
        assert data["affected"] == 1


class TestPauseSyncTasks:
    """Tests for POST /api/tasks/pause/sync."""

    def test_pause_sync_tasks(self, client):
        """Should pause sync task processing."""
        response = client.post("/api/tasks/pause/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is True


class TestResumeSyncTasks:
    """Tests for POST /api/tasks/resume/sync."""

    def test_resume_sync_tasks(self, client):
        """Should resume sync task processing."""
        response = client.post("/api/tasks/resume/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is False


class TestPauseDownloadTasks:
    """Tests for POST /api/tasks/pause/download."""

    def test_pause_download_tasks(self, client):
        """Should pause download task processing."""
        response = client.post("/api/tasks/pause/download")

        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is True


class TestResumeDownloadTasks:
    """Tests for POST /api/tasks/resume/download."""

    def test_resume_download_tasks(self, client):
        """Should resume download task processing."""
        response = client.post("/api/tasks/resume/download")

        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is False
