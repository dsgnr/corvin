import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.logging import get_logger
from app.extensions import SessionLocal

logger = get_logger("task_queue")


SETTING_WORKER_PAUSED = "worker_paused"
SETTING_SYNC_PAUSED = "sync_paused"
SETTING_DOWNLOAD_PAUSED = "download_paused"


class TaskWorker:
    """Task queue with thread pool workers. Uses SQLite for backend."""

    def __init__(
        self,
        max_sync_workers: int = 2,
        max_download_workers: int = 2,
        poll_interval: float = 30.0,
    ):
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
        self._task_event = threading.Event()

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
        self._task_event.set()  # Wake up the poll loop
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
        self._sync_executor.shutdown(wait=wait)
        self._download_executor.shutdown(wait=wait)
        logger.info("TaskWorker stopped")

    def notify(self) -> None:
        """Signal that new tasks are available for processing."""
        self._task_event.set()

    def pause(self, task_type: str | None = None) -> None:
        """Pause the worker from picking up new tasks (persisted to DB).

        Args:
            task_type: 'sync', 'download', or None for all
        """
        from app.models.settings import Settings

        with SessionLocal() as db:
            if task_type == "sync":
                Settings.set_bool(db, SETTING_SYNC_PAUSED, True)
                logger.info("Sync tasks paused")
            elif task_type == "download":
                Settings.set_bool(db, SETTING_DOWNLOAD_PAUSED, True)
                logger.info("Download tasks paused")
            else:
                Settings.set_bool(db, SETTING_WORKER_PAUSED, True)
                logger.info("All tasks paused")

    def resume(self, task_type: str | None = None) -> None:
        """Resume the worker to pick up new tasks (persisted to DB).

        Args:
            task_type: 'sync', 'download', or None for all
        """
        from app.models.settings import Settings

        with SessionLocal() as db:
            if task_type == "sync":
                Settings.set_bool(db, SETTING_SYNC_PAUSED, False)
                logger.info("Sync tasks resumed")
            elif task_type == "download":
                Settings.set_bool(db, SETTING_DOWNLOAD_PAUSED, False)
                logger.info("Download tasks resumed")
            else:
                Settings.set_bool(db, SETTING_WORKER_PAUSED, False)
                logger.info("All tasks resumed")
        self._task_event.set()  # Wake up to process pending tasks

    def is_paused(self, task_type: str | None = None) -> bool:
        """Check if the worker is paused (from DB).

        Args:
            task_type: 'sync', 'download', or None for global pause
        """
        from app.models.settings import Settings

        with SessionLocal() as db:
            # Global pause takes precedence
            if Settings.get_bool(db, SETTING_WORKER_PAUSED, False):
                return True
            if task_type == "sync":
                return Settings.get_bool(db, SETTING_SYNC_PAUSED, False)
            if task_type == "download":
                return Settings.get_bool(db, SETTING_DOWNLOAD_PAUSED, False)
            return False

    def _poll_loop(self) -> None:
        """Main loop that waits for task notifications or periodic fallback."""
        while not self._shutdown:
            try:
                self._process_pending_tasks()
            except Exception:
                logger.exception("Error in task poll loop")
            # Wait for notification or timeout (fallback poll)
            self._task_event.wait(timeout=self.poll_interval)
            self._task_event.clear()

    def _process_pending_tasks(self) -> None:
        """Check for pending tasks and submit to executors."""
        if not self.is_paused("sync"):
            self._process_task_type("sync", self._sync_executor, self.max_sync_workers)
        if not self.is_paused("download"):
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
        from app.models.task import Task, TaskStatus

        with self._lock:
            if task_type == "sync":
                available = max_workers - self._running_sync
            else:
                available = max_workers - self._running_download

            if available <= 0:
                return

            with SessionLocal() as db:
                tasks = (
                    db.query(Task)
                    .filter_by(task_type=task_type, status=TaskStatus.PENDING.value)
                    .order_by(Task.created_at.asc())
                    .limit(available)
                    .all()
                )

                if not tasks:
                    return

                # Increment counters while holding lock to prevent race conditions
                if task_type == "sync":
                    self._running_sync += len(tasks)
                    logger.info(
                        "Picked up %d sync tasks, running_sync now %d (max %d)",
                        len(tasks),
                        self._running_sync,
                        max_workers,
                    )
                else:
                    self._running_download += len(tasks)
                    logger.info(
                        "Picked up %d download tasks, running_download now %d (max %d)",
                        len(tasks),
                        self._running_download,
                        max_workers,
                    )

                # Now process tasks outside the lock
                for task in tasks:
                    task.status = TaskStatus.RUNNING.value
                    task.started_at = datetime.utcnow()
                    db.commit()

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
            self._run_task_handler(task_id, task_type)
        except Exception:
            logger.exception("Unhandled error executing task %d", task_id)
        finally:
            self._decrement_running_count(task_type)

    def _run_task_handler(self, task_id: int, task_type: str) -> None:
        """Run the task handler and update task status."""
        from app.models.task import Task, TaskLogLevel, TaskStatus

        with SessionLocal() as db:
            task = db.query(Task).get(task_id)
            if not task:
                logger.warning("Task %d not found", task_id)
                return

            handler = self._handlers.get(task_type)
            if not handler:
                self._fail_task(db, task, f"No handler for task type: {task_type}")
                return

            attempt = task.retry_count + 1
            task.add_log(
                db, f"Starting attempt {attempt}", TaskLogLevel.INFO.value, attempt
            )
            db.commit()

            try:
                result = handler(task.entity_id)
                task.status = TaskStatus.COMPLETED.value
                task.result = json.dumps(result) if result else None
                task.completed_at = datetime.utcnow()
                task.add_log(
                    db,
                    f"Completed successfully: {json.dumps(result) if result else 'OK'}",
                    TaskLogLevel.INFO.value,
                    attempt,
                )
                db.commit()
                logger.info("Task %d completed successfully", task_id)

            except Exception as e:
                self._handle_task_failure(db, task, e, attempt)

    def _fail_task(self, db, task, error_message: str) -> None:
        """Mark a task as failed."""
        from app.models.task import TaskLogLevel, TaskStatus

        task.status = TaskStatus.FAILED.value
        task.error = error_message
        task.completed_at = datetime.utcnow()
        task.add_log(db, f"Failed: {error_message}", TaskLogLevel.ERROR.value)
        db.commit()
        logger.error("Task %d failed: %s", task.id, error_message)

    def _handle_task_failure(
        self, db, task, exception: Exception, attempt: int
    ) -> None:
        """Handle task failure with retry logic."""
        from app.models.task import TaskLogLevel, TaskStatus

        error_msg = str(exception)
        task.error = error_msg
        task.retry_count += 1

        if task.retry_count < task.max_retries:
            task.status = TaskStatus.PENDING.value
            task.started_at = None
            task.add_log(
                db,
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
                db,
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

        db.commit()

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
                "paused": self.is_paused(),
                "sync_paused": self.is_paused("sync"),
                "download_paused": self.is_paused("download"),
            }


_worker: TaskWorker | None = None


def get_worker() -> TaskWorker | None:
    return _worker


def init_worker(max_sync_workers: int = 2, max_download_workers: int = 3) -> TaskWorker:
    global _worker
    _worker = TaskWorker(max_sync_workers, max_download_workers)
    return _worker
