import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from flask import Flask

from app.core.logging import get_logger

logger = get_logger("task_queue")


class TaskWorker:
    """Task queue with thread pool workers. Uses SQLite for backend"""

    def __init__(
        self,
        app: Flask,
        max_sync_workers: int = 2,
        max_download_workers: int = 3,
        poll_interval: float = 2.0,
    ):
        self.app = app
        self.max_sync_workers = max_sync_workers
        self.max_download_workers = max_download_workers
        self.poll_interval = poll_interval

        self._sync_executor = ThreadPoolExecutor(
            max_workers=max_sync_workers, thread_name_prefix="sync"
        )
        self._download_executor = ThreadPoolExecutor(
            max_workers=max_download_workers, thread_name_prefix="download"
        )

        self._running_sync = 0
        self._running_download = 0
        self._lock = threading.Lock()

        self._shutdown = False
        self._poll_thread: threading.Thread | None = None

        self._handlers: dict[str, Callable] = {}

        logger.info(
            "TaskWorker initialised with %d sync and %d download workers",
            max_sync_workers,
            max_download_workers,
        )

    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a handler function for a task type."""
        self._handlers[task_type] = handler
        logger.info("Registered handler for task type: %s", task_type)

    def start(self) -> None:
        """Start the background polling thread."""
        self._shutdown = False
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("TaskWorker started")

    def stop(self, wait: bool = True) -> None:
        """Stop the worker and try to wait for tasks to complete."""
        logger.info("TaskWorker stopping")
        self._shutdown = True
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
        self._sync_executor.shutdown(wait=wait)
        self._download_executor.shutdown(wait=wait)
        logger.info("TaskWorker stopped")

    def _poll_loop(self) -> None:
        """Main polling loop that picks up pending tasks."""
        while not self._shutdown:
            try:
                self._process_pending_tasks()
            except Exception:
                logger.exception("Error in task poll loop")
            time.sleep(self.poll_interval)

    def _process_pending_tasks(self) -> None:
        """Check for pending tasks and submit to executors."""
        with self.app.app_context():
            self._process_task_type("sync", self._sync_executor, self.max_sync_workers)
            self._process_task_type(
                "download", self._download_executor, self.max_download_workers
            )

    def _process_task_type(
        self,
        task_type: str,
        executor: ThreadPoolExecutor,
        max_workers: int,
    ) -> None:
        """Process pending tasks of a specific type."""
        from app.extensions import db
        from app.models.task import Task, TaskStatus

        with self._lock:
            if task_type == "sync":
                available = max_workers - self._running_sync
            else:
                available = max_workers - self._running_download

        if available <= 0:
            return

        tasks = (
            Task.query.filter_by(task_type=task_type, status=TaskStatus.PENDING.value)
            .order_by(Task.created_at.asc())
            .limit(available)
            .all()
        )

        for task in tasks:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            db.session.commit()

            with self._lock:
                if task_type == "sync":
                    self._running_sync += 1
                else:
                    self._running_download += 1

            logger.info(
                "Starting task %d (%s) for entity %d",
                task.id,
                task_type,
                task.entity_id,
            )
            executor.submit(self._execute_task, task.id, task_type)

    def _execute_task(self, task_id: int, task_type: str) -> None:
        """Execute a task."""
        try:
            with self.app.app_context():
                self._run_task_handler(task_id, task_type)
        except Exception:
            logger.exception("Unhandled error executing task %d", task_id)
        finally:
            self._decrement_running_count(task_type)

    def _run_task_handler(self, task_id: int, task_type: str) -> None:
        """Run the task handler and update task status."""
        from app.extensions import db
        from app.models.task import Task, TaskLogLevel, TaskStatus

        task = Task.query.get(task_id)
        if not task:
            logger.warning("Task %d not found", task_id)
            return

        handler = self._handlers.get(task_type)
        if not handler:
            self._fail_task(task, f"No handler for task type: {task_type}")
            return

        attempt = task.retry_count + 1
        task.add_log(f"Starting attempt {attempt}", TaskLogLevel.INFO.value, attempt)
        db.session.commit()

        try:
            result = handler(self.app, task.entity_id)
            task.status = TaskStatus.COMPLETED.value
            task.result = json.dumps(result) if result else None
            task.completed_at = datetime.utcnow()
            task.add_log(
                f"Completed successfully: {json.dumps(result) if result else 'OK'}",
                TaskLogLevel.INFO.value,
                attempt,
            )
            db.session.commit()
            logger.info("Task %d completed successfully", task_id)

        except Exception as e:
            self._handle_task_failure(task, e, attempt)

    def _fail_task(self, task, error_message: str) -> None:
        """Mark a task as failed."""
        from app.extensions import db
        from app.models.task import TaskLogLevel, TaskStatus

        task.status = TaskStatus.FAILED.value
        task.error = error_message
        task.completed_at = datetime.utcnow()
        task.add_log(f"Failed: {error_message}", TaskLogLevel.ERROR.value)
        db.session.commit()
        logger.error("Task %d failed: %s", task.id, error_message)

    def _handle_task_failure(self, task, exception: Exception, attempt: int) -> None:
        """Handle task failure with retry logic."""
        from app.extensions import db
        from app.models.task import TaskLogLevel, TaskStatus

        error_msg = str(exception)
        task.error = error_msg
        task.retry_count += 1

        if task.retry_count < task.max_retries:
            task.status = TaskStatus.PENDING.value
            task.started_at = None
            task.add_log(
                f"Failed (attempt {attempt}/{task.max_retries}): {error_msg}. Will retry.",
                TaskLogLevel.WARNING.value,
                attempt,
            )
            logger.warning(
                "Task %d failed (attempt %d/%d), will retry: %s",
                task.id,
                task.retry_count,
                task.max_retries,
                exception,
            )
        else:
            task.status = TaskStatus.FAILED.value
            task.completed_at = datetime.utcnow()
            task.add_log(
                f"Failed permanently after {attempt} attempts: {error_msg}",
                TaskLogLevel.ERROR.value,
                attempt,
            )
            logger.error(
                "Task %d failed permanently after %d attempts: %s",
                task.id,
                task.retry_count,
                exception,
            )

        db.session.commit()

    def _decrement_running_count(self, task_type: str) -> None:
        """Reduce the running task count."""
        with self._lock:
            if task_type == "sync":
                self._running_sync = max(0, self._running_sync - 1)
            else:
                self._running_download = max(0, self._running_download - 1)

    def get_stats(self) -> dict:
        """Get current worker stats."""
        with self._lock:
            return {
                "running_sync": self._running_sync,
                "running_download": self._running_download,
                "max_sync_workers": self.max_sync_workers,
                "max_download_workers": self.max_download_workers,
            }


_worker: TaskWorker | None = None


def get_worker() -> TaskWorker | None:
    return _worker


def init_worker(
    app: Flask, max_sync_workers: int = 2, max_download_workers: int = 3
) -> TaskWorker:
    global _worker
    _worker = TaskWorker(app, max_sync_workers, max_download_workers)
    return _worker
