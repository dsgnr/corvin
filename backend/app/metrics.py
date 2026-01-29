"""
Prometheus metrics for monitoring the application.

Exposes queue statistics, worker status, and entity counts at /metrics
in Prometheus format.
"""

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.helpers import _get_pyproject_attr
from app.extensions import SessionLocal

app_info = Info(_get_pyproject_attr("name"), _get_pyproject_attr("description"))

# Queue metrics
queue_pending = Gauge(
    "task_queue_pending",
    "Number of pending tasks in queue",
    ["task_type"],
)
queue_running = Gauge(
    "task_queue_running",
    "Number of currently running tasks",
    ["task_type"],
)
queue_workers_max = Gauge(
    "task_queue_workers_max",
    "Maximum number of workers configured",
    ["task_type"],
)
queue_workers_available = Gauge(
    "task_queue_workers_available",
    "Number of available workers",
    ["task_type"],
)
worker_paused = Gauge(
    "worker_paused",
    "Whether worker is paused (1=paused, 0=running)",
    ["task_type"],
)

# Task completion metrics (counters - monotonically increasing)
tasks_completed_total = Counter(
    "tasks_completed_total",
    "Total number of completed tasks",
    ["task_type"],
)
tasks_failed_total = Counter(
    "tasks_failed_total",
    "Total number of failed tasks",
    ["task_type"],
)

# Task duration histogram
task_duration_seconds = Histogram(
    "task_duration_seconds",
    "Task execution duration in seconds",
    ["task_type"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

# Entity counts
profiles_total = Gauge("profiles_total", "Total number of profiles")
lists_total = Gauge("lists_total", "Total number of video lists", ["enabled"])
videos_total = Gauge("videos_total", "Total number of videos", ["downloaded"])
videos_failed_total = Gauge("videos_failed_total", "Videos with download errors")

# Storage metrics
storage_bytes_total = Gauge("storage_bytes_total", "Total downloaded storage in bytes")


def init_metrics(app: FastAPI) -> Instrumentator:
    """
    Initialise Prometheus metrics.

    Args:
        app: The FastAPI application instance.

    Returns:
        The configured Instrumentator instance.
    """
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from starlette.responses import Response

    instrumentator = Instrumentator()
    instrumentator.instrument(app)

    # Custom /metrics endpoint that collects our metrics before generating output
    @app.get("/metrics", include_in_schema=True, tags=["Metrics"])
    def metrics():
        collect_queue_metrics()
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app_info.info(
        {
            "version": _get_pyproject_attr("version"),
            "name": _get_pyproject_attr("name"),
            "description": _get_pyproject_attr("description"),
        }
    )

    return instrumentator


def collect_queue_metrics() -> None:
    """
    Collect current queue metrics from the database and worker.

    Queries pending task counts from the database and running task counts
    from the worker. Called on each /metrics request to ensure fresh data.
    """
    from app.models.task import Task, TaskStatus, TaskType
    from app.task_queue import get_worker

    with SessionLocal() as db:
        # Pending tasks from database
        pending_sync = (
            db.query(Task)
            .filter_by(task_type=TaskType.SYNC.value, status=TaskStatus.PENDING.value)
            .count()
        )
        pending_download = (
            db.query(Task)
            .filter_by(
                task_type=TaskType.DOWNLOAD.value, status=TaskStatus.PENDING.value
            )
            .count()
        )

    queue_pending.labels(task_type="sync").set(pending_sync)
    queue_pending.labels(task_type="download").set(pending_download)

    # Running tasks and worker stats
    worker = get_worker()
    if worker:
        stats = worker.get_stats()
        queue_running.labels(task_type="sync").set(stats["running_sync"])
        queue_running.labels(task_type="download").set(stats["running_download"])
        queue_workers_max.labels(task_type="sync").set(stats["max_sync_workers"])
        queue_workers_max.labels(task_type="download").set(
            stats["max_download_workers"]
        )
        queue_workers_available.labels(task_type="sync").set(
            stats["max_sync_workers"] - stats["running_sync"]
        )
        queue_workers_available.labels(task_type="download").set(
            stats["max_download_workers"] - stats["running_download"]
        )
        # Pause state
        worker_paused.labels(task_type="sync").set(1 if stats["sync_paused"] else 0)
        worker_paused.labels(task_type="download").set(
            1 if stats["download_paused"] else 0
        )
        worker_paused.labels(task_type="all").set(1 if stats["paused"] else 0)
    else:
        # Worker not initialised (e.g., during testing)
        for task_type in ["sync", "download", "all"]:
            queue_running.labels(task_type=task_type).set(0)
            queue_workers_max.labels(task_type=task_type).set(0)
            queue_workers_available.labels(task_type=task_type).set(0)
            worker_paused.labels(task_type=task_type).set(0)

    # Entity counts
    _collect_entity_metrics()


def _collect_entity_metrics() -> None:
    """
    Collect entity count metrics (profiles, lists, videos).

    Breaks down lists by enabled/disabled and videos by downloaded/pending/failed.
    """
    from sqlalchemy import func

    from app.models.profile import Profile
    from app.models.video import Video
    from app.models.video_list import VideoList

    with SessionLocal() as db:
        profiles_total.set(db.query(Profile).count())

        lists_total.labels(enabled="true").set(
            db.query(VideoList).filter_by(enabled=True).count()
        )
        lists_total.labels(enabled="false").set(
            db.query(VideoList).filter_by(enabled=False).count()
        )

        videos_total.labels(downloaded="true").set(
            db.query(Video).filter_by(downloaded=True).count()
        )
        videos_total.labels(downloaded="false").set(
            db.query(Video).filter_by(downloaded=False).count()
        )

        # Videos with errors
        videos_failed_total.set(
            db.query(Video).filter(Video.error_message.isnot(None)).count()
        )

        # Storage: sum of filesize from downloaded videos
        total_bytes = (
            db.query(func.sum(Video.filesize))
            .filter(Video.downloaded.is_(True))
            .scalar()
        )
        storage_bytes_total.set(total_bytes or 0)
