"""Prometheus metrics for the application."""

from flask import Flask
from prometheus_client import Gauge, Info
from prometheus_flask_exporter import PrometheusMetrics

from app.core.helpers import _get_pyproject_attr

_pyproject_data: dict | None = None

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


def init_metrics(app: Flask) -> PrometheusMetrics:
    """Initialise Prometheus metrics for the Flask app."""
    # Disable default endpoint, we'll register manually to work in debug mode
    metrics = PrometheusMetrics(app, path=None, defaults_prefix="flask")
    metrics.register_endpoint("/metrics")

    app_info.info(
        {
            "version": _get_pyproject_attr("version"),
            "name": _get_pyproject_attr("name"),
            "description": _get_pyproject_attr("description"),
        }
    )

    @app.before_request
    def update_queue_metrics():
        """Update queue metrics on each request to /metrics."""
        from flask import request

        if request.path == "/metrics":
            _collect_queue_metrics(app)

    return metrics


def _collect_queue_metrics(app: Flask) -> None:
    """Collect current queue metrics from database and worker."""
    from app.models.task import Task, TaskStatus, TaskType
    from app.task_queue import get_worker

    # Pending tasks from database
    pending_sync = Task.query.filter_by(
        task_type=TaskType.SYNC.value, status=TaskStatus.PENDING.value
    ).count()
    pending_download = Task.query.filter_by(
        task_type=TaskType.DOWNLOAD.value, status=TaskStatus.PENDING.value
    ).count()

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

    profiles_total.set(Profile.query.count())

    lists_total.labels(enabled="true").set(
        VideoList.query.filter_by(enabled=True).count()
    )
    lists_total.labels(enabled="false").set(
        VideoList.query.filter_by(enabled=False).count()
    )

    videos_total.labels(downloaded="true").set(
        Video.query.filter_by(downloaded=True).count()
    )
    videos_total.labels(downloaded="false").set(
        Video.query.filter_by(downloaded=False).count()
    )
