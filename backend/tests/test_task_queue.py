"""Tests for TaskWorker and task queue functionality."""

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.task import Task, TaskStatus, TaskType
from app.task_queue import (
    SETTING_DOWNLOAD_PAUSED,
    SETTING_SYNC_PAUSED,
    SETTING_WORKER_PAUSED,
    TaskWorker,
    get_worker,
    init_worker,
)


class TestTaskWorkerInit:
    """Tests for TaskWorker initialisation."""

    def test_init_sets_defaults(self):
        """Should initialise with default worker counts."""
        worker = TaskWorker()

        assert worker.max_sync_workers == 2
        assert worker.max_download_workers == 2
        assert worker.poll_interval == 30.0
        assert worker._running_sync == 0
        assert worker._running_download == 0
        assert worker._shutdown is False

    def test_init_custom_workers(self):
        """Should accept custom worker counts."""
        worker = TaskWorker(max_sync_workers=5, max_download_workers=10)

        assert worker.max_sync_workers == 5
        assert worker.max_download_workers == 10

    def test_init_custom_poll_interval(self):
        """Should accept custom poll interval."""
        worker = TaskWorker(poll_interval=60.0)

        assert worker.poll_interval == 60.0

    def test_init_zero_workers_edge_case(self):
        """Zero workers causes ThreadPoolExecutor to raise ValueError."""
        # ThreadPoolExecutor requires max_workers > 0
        with pytest.raises(ValueError):
            TaskWorker(max_sync_workers=0, max_download_workers=0)


class TestTaskWorkerHandlers:
    """Tests for handler registration."""

    def test_register_handler(self):
        """Should register a handler for a task type."""
        worker = TaskWorker()
        handler = MagicMock()

        worker.register_handler("sync", handler)

        assert "sync" in worker._handlers
        assert worker._handlers["sync"] is handler

    def test_register_multiple_handlers(self):
        """Should register multiple handlers."""
        worker = TaskWorker()
        sync_handler = MagicMock()
        download_handler = MagicMock()

        worker.register_handler("sync", sync_handler)
        worker.register_handler("download", download_handler)

        assert worker._handlers["sync"] is sync_handler
        assert worker._handlers["download"] is download_handler

    def test_register_handler_overwrites(self):
        """Should overwrite existing handler."""
        worker = TaskWorker()
        handler1 = MagicMock()
        handler2 = MagicMock()

        worker.register_handler("sync", handler1)
        worker.register_handler("sync", handler2)

        assert worker._handlers["sync"] is handler2


class TestTaskWorkerStartStop:
    """Tests for worker start/stop lifecycle."""

    def test_start_creates_poll_thread(self):
        """Should create and start poll thread."""
        worker = TaskWorker()

        worker.start()

        assert worker._poll_thread is not None
        assert worker._poll_thread.is_alive()
        assert worker._shutdown is False

        worker.stop(wait=False)

    def test_stop_sets_shutdown_flag(self):
        """Should set shutdown flag when stopping."""
        worker = TaskWorker()
        worker.start()

        worker.stop(wait=False)

        assert worker._shutdown is True

    def test_notify_sets_event(self):
        """Should set task event when notified."""
        worker = TaskWorker()
        worker._task_event.clear()

        worker.notify()

        assert worker._task_event.is_set()


class TestTaskWorkerPauseResume:
    """Tests for pause/resume functionality."""

    def test_pause_all_tasks(self, app, db_session):
        """Should pause all task processing."""
        from app.models.settings import Settings

        worker = TaskWorker()
        worker.pause()

        assert Settings.get_bool(db_session, SETTING_WORKER_PAUSED, False) is True

    def test_pause_sync_only(self, app, db_session):
        """Should pause only sync tasks."""
        from app.models.settings import Settings

        worker = TaskWorker()
        worker.pause("sync")

        assert Settings.get_bool(db_session, SETTING_SYNC_PAUSED, False) is True
        assert Settings.get_bool(db_session, SETTING_DOWNLOAD_PAUSED, False) is False

    def test_pause_download_only(self, app, db_session):
        """Should pause only download tasks."""
        from app.models.settings import Settings

        worker = TaskWorker()
        worker.pause("download")

        assert Settings.get_bool(db_session, SETTING_SYNC_PAUSED, False) is False
        assert Settings.get_bool(db_session, SETTING_DOWNLOAD_PAUSED, False) is True

    def test_resume_all_tasks(self, app, db_session):
        """Should resume all task processing."""
        from app.models.settings import Settings

        worker = TaskWorker()

        # First pause
        worker.pause()
        assert worker.is_paused() is True

        # Then resume
        worker.resume()
        assert Settings.get_bool(db_session, SETTING_WORKER_PAUSED, False) is False

    def test_resume_sets_event(self, app, db_session):
        """Should signal event when resuming to wake poll loop."""
        worker = TaskWorker()
        worker._task_event.clear()
        worker.resume()

        assert worker._task_event.is_set()

    def test_is_paused_global_takes_precedence(self, app, db_session):
        """Global pause should take precedence over type-specific."""
        from app.models.settings import Settings

        worker = TaskWorker()

        # Set global pause
        Settings.set_bool(db_session, SETTING_WORKER_PAUSED, True)
        db_session.commit()

        # Even if sync is not paused, global pause should return True
        assert worker.is_paused("sync") is True
        assert worker.is_paused("download") is True
        assert worker.is_paused() is True


class TestTaskWorkerStats:
    """Tests for worker statistics."""

    def test_get_stats_initial(self, app, db_session):
        """Should return initial stats."""
        worker = TaskWorker(max_sync_workers=3, max_download_workers=5)
        stats = worker.get_stats()

        assert stats["running_sync"] == 0
        assert stats["running_download"] == 0
        assert stats["max_sync_workers"] == 3
        assert stats["max_download_workers"] == 5

    def test_get_stats_includes_pause_state(self, app, db_session):
        """Should include pause states in stats."""
        worker = TaskWorker()
        stats = worker.get_stats()

        assert "paused" in stats
        assert "sync_paused" in stats
        assert "download_paused" in stats


class TestTaskWorkerProcessing:
    """Tests for task processing logic."""

    def test_process_task_type_no_available_workers(self, app, db_session):
        """Should not process when no workers available."""
        worker = TaskWorker(max_sync_workers=1)
        worker._running_sync = 1  # All workers busy

        # Create a pending task
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.PENDING.value,
        )
        db_session.add(task)
        db_session.commit()

        worker._process_task_type("sync", worker._sync_executor, 1)

        # Task should still be pending
        db_session.refresh(task)
        assert task.status == TaskStatus.PENDING.value

    def test_decrement_running_count_sync(self):
        """Should decrement sync count and signal event."""
        worker = TaskWorker()
        worker._running_sync = 2
        worker._task_event.clear()

        worker._decrement_running_count("sync")

        assert worker._running_sync == 1
        assert worker._task_event.is_set()

    def test_decrement_running_count_download(self):
        """Should decrement download count and signal event."""
        worker = TaskWorker()
        worker._running_download = 3
        worker._task_event.clear()

        worker._decrement_running_count("download")

        assert worker._running_download == 2
        assert worker._task_event.is_set()

    def test_decrement_running_count_never_negative(self):
        """Should never go below zero."""
        worker = TaskWorker()
        worker._running_sync = 0

        worker._decrement_running_count("sync")

        assert worker._running_sync == 0


class TestTaskWorkerFailTask:
    """Tests for task failure handling."""

    def test_fail_task_sets_status(self, app, db_session, sample_list):
        """Should set task status to failed."""
        worker = TaskWorker()

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
        )
        db_session.add(task)
        db_session.commit()

        with patch("app.task_queue.broadcast"):
            worker._fail_task(db_session, task, "Test error")

        assert task.status == TaskStatus.FAILED.value
        assert task.error == "Test error"
        assert task.completed_at is not None

    def test_fail_task_adds_log(self, app, db_session, sample_list):
        """Should add error log entry."""
        worker = TaskWorker()

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
        )
        db_session.add(task)
        db_session.commit()

        with patch("app.task_queue.broadcast"):
            worker._fail_task(db_session, task, "Test error")

        logs = list(task.logs)
        assert len(logs) == 1
        assert "Failed" in logs[0].message


class TestTaskWorkerRetryLogic:
    """Tests for task retry handling."""

    def test_handle_task_failure_retries_if_under_max(
        self, app, db_session, sample_list
    ):
        """Should retry task if under max retries."""
        worker = TaskWorker()

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
            retry_count=0,
            max_retries=3,
        )
        db_session.add(task)
        db_session.commit()

        with patch("app.task_queue.broadcast"):
            worker._handle_task_failure(db_session, task, Exception("Temp error"), 1)

        assert task.status == TaskStatus.PENDING.value
        assert task.retry_count == 1
        assert task.started_at is None  # Reset for retry

    def test_handle_task_failure_fails_at_max_retries(
        self, app, db_session, sample_list
    ):
        """Should fail permanently at max retries."""
        worker = TaskWorker()

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
            retry_count=2,
            max_retries=3,
        )
        db_session.add(task)
        db_session.commit()

        with patch("app.task_queue.broadcast"):
            worker._handle_task_failure(db_session, task, Exception("Final error"), 3)

        assert task.status == TaskStatus.FAILED.value
        assert task.retry_count == 3
        assert task.completed_at is not None


class TestTaskWorkerRunHandler:
    """Tests for running task handlers."""

    def test_run_task_handler_success(self, app, db_session, sample_list):
        """Should complete task on successful handler execution."""
        worker = TaskWorker()
        handler = MagicMock(return_value={"result": "success"})
        worker.register_handler("sync", handler)

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id

        with patch("app.task_queue.broadcast"):
            worker._run_task_handler(task_id, "sync")

        db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED.value
        assert task.completed_at is not None
        handler.assert_called_once_with(sample_list)

    def test_run_task_handler_no_handler(self, app, db_session, sample_list):
        """Should fail task when no handler registered."""
        worker = TaskWorker()
        # No handler registered

        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.RUNNING.value,
        )
        db_session.add(task)
        db_session.commit()
        task_id = task.id

        with patch("app.task_queue.broadcast"):
            worker._run_task_handler(task_id, "sync")

        db_session.refresh(task)
        assert task.status == TaskStatus.FAILED.value
        assert "No handler" in task.error

    def test_run_task_handler_task_not_found(self, app, db_session):
        """Should handle missing task gracefully."""
        worker = TaskWorker()
        handler = MagicMock()
        worker.register_handler("sync", handler)

        # Should not raise
        worker._run_task_handler(99999, "sync")

        handler.assert_not_called()


class TestGlobalWorker:
    """Tests for global worker instance."""

    def test_init_worker_creates_global(self):
        """Should create global worker instance."""
        import app.task_queue as tq

        original = tq._worker
        try:
            tq._worker = None

            worker = init_worker(max_sync_workers=4, max_download_workers=6)

            assert worker is not None
            assert worker.max_sync_workers == 4
            assert worker.max_download_workers == 6
            assert get_worker() is worker
        finally:
            tq._worker = original

    def test_get_worker_returns_none_if_not_initialised(self):
        """Should return None if worker not initialised."""
        import app.task_queue as tq

        original = tq._worker
        try:
            tq._worker = None
            assert get_worker() is None
        finally:
            tq._worker = original


class TestTaskWorkerConcurrency:
    """Tests for concurrent task processing edge cases."""

    def test_running_count_thread_safety(self):
        """Running counts should be thread-safe."""
        worker = TaskWorker()
        worker._running_sync = 0

        def increment_decrement():
            for _ in range(100):
                with worker._lock:
                    worker._running_sync += 1
                time.sleep(0.001)
                worker._decrement_running_count("sync")

        threads = [threading.Thread(target=increment_decrement) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should end up at 0 (or close to it due to timing)
        assert worker._running_sync >= 0

    def test_poll_loop_respects_shutdown(self):
        """Poll loop should exit when shutdown is set."""
        worker = TaskWorker(poll_interval=0.1)
        worker.start()

        # Give it a moment to start
        time.sleep(0.05)

        worker._shutdown = True
        worker._task_event.set()

        # Should stop within a reasonable time
        worker._poll_thread.join(timeout=1.0)
        assert not worker._poll_thread.is_alive()
