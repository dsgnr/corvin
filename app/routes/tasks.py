from flask import Blueprint, request, jsonify

from app.extensions import db
from app.core.exceptions import NotFoundError, ValidationError, ConflictError
from app.core.logging import get_logger
from app.models.task import Task, TaskStatus, TaskType
from app.task_queue import get_worker
from app.tasks import enqueue_task, schedule_all_syncs, schedule_pending_downloads

logger = get_logger("routes.tasks")
bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.get("/")
def list_tasks():
    """List tasks with optional filtering."""
    task_type = request.args.get("type")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    query = Task.query.order_by(Task.created_at.desc())

    if task_type:
        query = query.filter_by(task_type=task_type)
    if status:
        query = query.filter_by(status=status)

    tasks = query.offset(offset).limit(limit).all()
    return jsonify([t.to_dict() for t in tasks])


@bp.get("/<int:task_id>")
def get_task(task_id: int):
    """Get a task by ID."""
    task = Task.query.get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    return jsonify(task.to_dict())


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


@bp.post("/sync/list/<int:list_id>")
def trigger_list_sync(list_id: int):
    """Trigger a sync for a specific list."""
    task = enqueue_task(TaskType.SYNC.value, list_id)

    if not task:
        raise ConflictError("List sync already queued or running")

    logger.info("Triggered sync for list %d", list_id)
    return jsonify(task.to_dict()), 202


@bp.post("/sync/all")
def trigger_all_syncs():
    """Trigger sync for all enabled lists."""
    queued = schedule_all_syncs()
    logger.info("Triggered sync for all lists: %d queued", queued)
    return jsonify({"queued": queued}), 202


@bp.post("/download/video/<int:video_id>")
def trigger_video_download(video_id: int):
    """Trigger download for a specific video."""
    task = enqueue_task(TaskType.DOWNLOAD.value, video_id)

    if not task:
        raise ConflictError("Video download already queued or running")

    logger.info("Triggered download for video %d", video_id)
    return jsonify(task.to_dict()), 202


@bp.post("/download/pending")
def trigger_pending_downloads():
    """Trigger download for all pending videos."""
    queued = schedule_pending_downloads()
    logger.info("Triggered pending downloads: %d queued", queued)
    return jsonify({"queued": queued}), 202


@bp.post("/<int:task_id>/retry")
def retry_task(task_id: int):
    """Retry a failed or completed task."""
    task = Task.query.get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

    if task.status not in (TaskStatus.FAILED.value, TaskStatus.COMPLETED.value):
        raise ValidationError("Can only retry failed or completed tasks")

    task.status = TaskStatus.PENDING.value
    task.error = None
    task.started_at = None
    task.completed_at = None
    task.retry_count = 0
    db.session.commit()

    logger.info("Task %d reset for retry", task_id)
    return jsonify(task.to_dict())
