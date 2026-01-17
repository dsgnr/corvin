"""Prometheus metrics for the application."""

from fastapi import FastAPI
from prometheus_client import Gauge, Info
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

# Entity counts
profiles_total = Gauge("profiles_total", "Total number of profiles")
lists_total = Gauge("lists_total", "Total number of video lists", ["enabled"])
videos_total = Gauge("videos_total", "Total number of videos", ["downloaded"])


def init_metrics(app: FastAPI) -> Instrumentator:
    """Initialise Prometheus metrics for the FastAPI app."""
    instrumentator = Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    app_info.info(
        {
            "version": _get_pyproject_attr("version"),
            "name": _get_pyproject_attr("name"),
            "description": _get_pyproject_attr("description"),
        }
    )

    return instrumentator


def collect_queue_metrics() -> None:
    """Collect current queue metrics from database and worker."""
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
    else:
        # Worker not initialised (e.g., during testing)
        for task_type in ["sync", "download"]:
            queue_running.labels(task_type=task_type).set(0)
            queue_workers_max.labels(task_type=task_type).set(0)
            queue_workers_available.labels(task_type=task_type).set(0)

    # Entity counts
    _collect_entity_metrics()


def _collect_entity_metrics() -> None:
    """Collect entity count metrics."""
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
