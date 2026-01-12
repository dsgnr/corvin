import json
import time

from flask import Response, current_app, jsonify, request
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import func

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models.task import Task, TaskLog, TaskStatus, TaskType
from app.models.video import Video
from app.schemas.tasks import (
    ActiveTasksQuery,
    BulkDownloadRequest,
    BulkSyncRequest,
    ListIdPath,
    TaskLogsQuery,
    TaskPath,
    TaskQuery,
    VideoIdPath,
)
from app.task_queue import get_worker
from app.tasks import enqueue_task, schedule_downloads, schedule_syncs

logger = get_logger("routes.tasks")
tag = Tag(name="Tasks", description="Background task management")
bp = APIBlueprint("tasks", __name__, url_prefix="/api/tasks", abp_tags=[tag])


def _get_tasks_fingerprint(task_type: str | None, status: str | None) -> tuple:
    """Get fingerprint for change detection."""
    q = db.session.query(func.count(Task.id), func.max(Task.created_at))
    if task_type:
        q = q.filter(Task.task_type == task_type)
    if status:
        q = q.filter(Task.status == status)
    stats = q.first()
    return (stats[0], str(stats[1]) if stats[1] else None)


def _get_tasks_for_stream(
    task_type: str | None, status: str | None, limit: int | None
) -> list[dict]:
    """Get task data optimised for SSE stream."""
    q = Task.query.order_by(Task.created_at.desc())
    if task_type:
        q = q.filter_by(task_type=task_type)
    if status:
        q = q.filter_by(status=status)
    if limit:
        q = q.limit(limit)
    return [t.to_dict() for t in q.all()]


@bp.get("/")
def list_tasks(query: TaskQuery):
    """List tasks with optional filtering.

    If Accept header is 'text/event-stream', streams updates via SSE.
    Otherwise returns JSON array of tasks.
    """
    # Regular JSON response (early return)
    if request.accept_mimetypes.best != "text/event-stream":
        q = Task.query.order_by(Task.created_at.desc())
        if query.type:
            q = q.filter_by(task_type=query.type)
        if query.status:
            q = q.filter_by(status=query.status)
        q = q.offset(query.offset)
        if query.limit:
            q = q.limit(query.limit)
        return jsonify([t.to_dict() for t in q.all()])

    # SSE stream
    app = current_app._get_current_object()
    task_type = query.type
    status = query.status
    limit = query.limit

    def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with app.app_context():
                fingerprint = _get_tasks_fingerprint(task_type, status)

                if fingerprint != last_fingerprint:
                    data = _get_tasks_for_stream(task_type, status, limit)
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                    last_fingerprint = fingerprint
                    heartbeat_counter = 0
                else:
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:
                        yield ": heartbeat\n\n"
                        heartbeat_counter = 0

            time.sleep(1)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.get("/<int:task_id>")
def get_task(path: TaskPath, query: TaskLogsQuery):
    """Get a task by ID with optional logs."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)
    return jsonify(task.to_dict(include_logs=query.include_logs))


@bp.get("/<int:task_id>/logs")
def get_task_logs(path: TaskPath):
    """Get logs for a specific task."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)

    logs = task.logs.order_by(TaskLog.created_at.asc()).all()
    return jsonify([log.to_dict() for log in logs])


@bp.get("/stats")
def task_stats():
    """Get task queue statistics."""
    stats = {
        "pending_sync": Task.query.filter_by(
            task_type=TaskType.SYNC.value, status=TaskStatus.PENDING.value
        ).count(),
        "pending_download": Task.query.filter_by(
            task_type=TaskType.DOWNLOAD.value, status=TaskStatus.PENDING.value
        ).count(),
        "running_sync": Task.query.filter_by(
            task_type=TaskType.SYNC.value, status=TaskStatus.RUNNING.value
        ).count(),
        "running_download": Task.query.filter_by(
            task_type=TaskType.DOWNLOAD.value, status=TaskStatus.RUNNING.value
        ).count(),
    }

    worker = get_worker()
    if worker:
        stats["worker"] = worker.get_stats()

    return jsonify(stats)


@bp.get("/active")
def get_active_tasks(query: ActiveTasksQuery):
    """Get all pending and running tasks, grouped by type and status."""
    active_statuses = [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]

    result = {
        "sync": {"pending": [], "running": []},
        "download": {"pending": [], "running": []},
    }

    if query.list_id:
        sync_tasks = Task.query.filter(
            Task.task_type == TaskType.SYNC.value,
            Task.status.in_(active_statuses),
            Task.entity_id == query.list_id,
        ).all()

        video_ids = [
            v.id
            for v in Video.query.filter_by(list_id=query.list_id)
            .with_entities(Video.id)
            .all()
        ]

        download_tasks = []
        if video_ids:
            download_tasks = Task.query.filter(
                Task.task_type == TaskType.DOWNLOAD.value,
                Task.status.in_(active_statuses),
                Task.entity_id.in_(video_ids),
            ).all()

        tasks = sync_tasks + download_tasks
    else:
        tasks = Task.query.filter(Task.status.in_(active_statuses)).all()

    for task in tasks:
        task_type = task.task_type
        status = task.status
        if task_type in result and status in result[task_type]:
            result[task_type][status].append(task.entity_id)

    return jsonify(result)


@bp.post("/sync/list/<int:list_id>")
def trigger_list_sync(path: ListIdPath):
    """Trigger a sync for a specific list."""
    task = enqueue_task(TaskType.SYNC.value, path.list_id)

    if not task:
        raise ConflictError("List sync already queued or running")

    logger.info("Triggered sync for list %d", path.list_id)
    return jsonify(task.to_dict()), 202


@bp.post("/sync/lists")
def trigger_lists_sync(body: BulkSyncRequest):
    """Trigger sync for multiple lists by ID."""
    result = schedule_syncs(body.list_ids)
    logger.info(
        "Triggered sync for %d lists: %d queued", len(body.list_ids), result["queued"]
    )
    return jsonify({"queued": result["queued"], "skipped": result["skipped"]}), 202


@bp.post("/sync/all")
def trigger_all_syncs():
    """Trigger sync for all enabled lists."""
    result = schedule_syncs()
    logger.info("Triggered sync for all lists: %d queued", result["queued"])
    return jsonify({"queued": result["queued"], "skipped": result["skipped"]}), 202


@bp.post("/download/video/<int:video_id>")
def trigger_video_download(path: VideoIdPath):
    """Trigger download for a specific video."""
    task = enqueue_task(TaskType.DOWNLOAD.value, path.video_id)

    if not task:
        raise ConflictError("Video download already queued or running")

    logger.info("Triggered download for video %d", path.video_id)
    return jsonify(task.to_dict()), 202


@bp.post("/download/videos")
def trigger_videos_download(body: BulkDownloadRequest):
    """Trigger download for multiple videos by ID."""
    result = schedule_downloads(body.video_ids)
    logger.info(
        "Triggered download for %d videos: %d queued",
        len(body.video_ids),
        result["queued"],
    )
    return jsonify({"queued": result["queued"], "skipped": result["skipped"]}), 202


@bp.post("/download/pending")
def trigger_pending_downloads():
    """Trigger download for all pending videos."""
    result = schedule_downloads()
    logger.info("Triggered pending downloads: %d queued", result["queued"])
    return jsonify({"queued": result["queued"], "skipped": result["skipped"]}), 202


@bp.post("/<int:task_id>/retry")
def retry_task(path: TaskPath):
    """Retry a failed or completed task."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)

    if task.status not in (TaskStatus.FAILED.value, TaskStatus.COMPLETED.value):
        raise ValidationError("Can only retry failed or completed tasks")

    task.status = TaskStatus.PENDING.value
    task.error = None
    task.started_at = None
    task.completed_at = None
    task.retry_count = 0
    db.session.commit()

    logger.info("Task %d reset for retry", path.task_id)
    return jsonify(task.to_dict())
