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
    BulkTaskIdsRequest,
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


def _get_tasks_fingerprint(
    task_type: str | None, status: str | None, limit: int | None
) -> str:
    """Get fingerprint for change detection based on task statuses."""
    q = Task.query.order_by(Task.created_at.desc())
    if task_type:
        q = q.filter_by(task_type=task_type)
    if status:
        q = q.filter_by(status=status)
    if limit:
        q = q.limit(limit)
    # Create fingerprint from id:status pairs
    tasks = q.with_entities(Task.id, Task.status).all()
    return ",".join(f"{t.id}:{t.status}" for t in tasks)


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
                fingerprint = _get_tasks_fingerprint(task_type, status, limit)

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


def _get_stats_counts() -> dict:
    """Get all task stats in a single query using conditional aggregation."""
    result = (
        db.session.query(
            func.sum(
                db.case(
                    (
                        db.and_(
                            Task.task_type == TaskType.SYNC.value,
                            Task.status == TaskStatus.PENDING.value,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_sync"),
            func.sum(
                db.case(
                    (
                        db.and_(
                            Task.task_type == TaskType.DOWNLOAD.value,
                            Task.status == TaskStatus.PENDING.value,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_download"),
            func.sum(
                db.case(
                    (
                        db.and_(
                            Task.task_type == TaskType.SYNC.value,
                            Task.status == TaskStatus.RUNNING.value,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("running_sync"),
            func.sum(
                db.case(
                    (
                        db.and_(
                            Task.task_type == TaskType.DOWNLOAD.value,
                            Task.status == TaskStatus.RUNNING.value,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("running_download"),
        )
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
        .first()
    )
    return {
        "pending_sync": result.pending_sync or 0,
        "pending_download": result.pending_download or 0,
        "running_sync": result.running_sync or 0,
        "running_download": result.running_download or 0,
    }


@bp.get("/stats")
def task_stats():
    """Get task queue statistics.

    If Accept header is 'text/event-stream', streams updates via SSE.
    Otherwise returns JSON object of stats.
    """
    # Regular JSON response (early return)
    if request.accept_mimetypes.best != "text/event-stream":
        stats = _get_stats_counts()
        worker = get_worker()
        if worker:
            stats["worker"] = worker.get_stats()
        return jsonify(stats)

    # SSE stream
    app = current_app._get_current_object()

    def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with app.app_context():
                counts = _get_stats_counts()
                worker = get_worker()
                worker_stats = worker.get_stats() if worker else {}
                # Include pause states in fingerprint
                fingerprint = (
                    tuple(counts.values()),
                    worker_stats.get("paused"),
                    worker_stats.get("sync_paused"),
                    worker_stats.get("download_paused"),
                )

                if fingerprint != last_fingerprint:
                    if worker:
                        counts["worker"] = worker_stats
                    yield f"data: {json.dumps(counts, default=str)}\n\n"
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
    result = schedule_syncs(force=True)
    logger.info("Force triggered a sync for all lists: %d queued", result["queued"])
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

    if task.status not in (
        TaskStatus.FAILED.value,
        TaskStatus.COMPLETED.value,
        TaskStatus.CANCELLED.value,
    ):
        raise ValidationError("Can only retry failed, completed, or cancelled tasks")

    task.status = TaskStatus.PENDING.value
    task.error = None
    task.started_at = None
    task.completed_at = None
    task.retry_count = 0
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.notify()

    logger.info("Task %d reset for retry", path.task_id)
    return jsonify(task.to_dict())


@bp.post("/<int:task_id>/pause")
def pause_task(path: TaskPath):
    """Pause a pending task."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)

    if task.status != TaskStatus.PENDING.value:
        raise ValidationError("Can only pause pending tasks")

    task.status = TaskStatus.PAUSED.value
    db.session.commit()

    logger.info("Task %d paused", path.task_id)
    return jsonify(task.to_dict())


@bp.post("/<int:task_id>/resume")
def resume_task(path: TaskPath):
    """Resume a paused task."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)

    if task.status != TaskStatus.PAUSED.value:
        raise ValidationError("Can only resume paused tasks")

    task.status = TaskStatus.PENDING.value
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.notify()

    logger.info("Task %d resumed", path.task_id)
    return jsonify(task.to_dict())


@bp.post("/<int:task_id>/cancel")
def cancel_task(path: TaskPath):
    """Cancel a pending or paused task."""
    task = Task.query.get(path.task_id)
    if not task:
        raise NotFoundError("Task", path.task_id)

    if task.status not in (TaskStatus.PENDING.value, TaskStatus.PAUSED.value):
        raise ValidationError("Can only cancel pending or paused tasks")

    task.status = TaskStatus.CANCELLED.value
    task.completed_at = db.func.now()
    db.session.commit()

    logger.info("Task %d cancelled", path.task_id)
    return jsonify(task.to_dict())


@bp.post("/pause")
def pause_tasks(body: BulkTaskIdsRequest):
    """Pause multiple pending tasks."""
    affected = Task.query.filter(
        Task.id.in_(body.task_ids), Task.status == TaskStatus.PENDING.value
    ).update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    db.session.commit()

    skipped = len(body.task_ids) - affected
    logger.info("Paused %d tasks, skipped %d", affected, skipped)
    return jsonify({"affected": affected, "skipped": skipped})


@bp.post("/resume")
def resume_tasks(body: BulkTaskIdsRequest):
    """Resume multiple paused tasks."""
    affected = Task.query.filter(
        Task.id.in_(body.task_ids), Task.status == TaskStatus.PAUSED.value
    ).update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    db.session.commit()

    worker = get_worker()
    if worker and affected > 0:
        worker.notify()

    skipped = len(body.task_ids) - affected
    logger.info("Resumed %d tasks, skipped %d", affected, skipped)
    return jsonify({"affected": affected, "skipped": skipped})


@bp.post("/cancel")
def cancel_tasks(body: BulkTaskIdsRequest):
    """Cancel multiple pending or paused tasks."""
    affected = Task.query.filter(
        Task.id.in_(body.task_ids),
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.PAUSED.value]),
    ).update(
        {"status": TaskStatus.CANCELLED.value, "completed_at": db.func.now()},
        synchronize_session=False,
    )
    db.session.commit()

    skipped = len(body.task_ids) - affected
    logger.info("Cancelled %d tasks, skipped %d", affected, skipped)
    return jsonify({"affected": affected, "skipped": skipped})


@bp.post("/pause/all")
def pause_all_tasks():
    """Pause all pending tasks and stop the worker from picking up new tasks."""
    affected = Task.query.filter(Task.status == TaskStatus.PENDING.value).update(
        {"status": TaskStatus.PAUSED.value}, synchronize_session=False
    )
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.pause()

    logger.info("Paused all %d pending tasks and worker", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/resume/all")
def resume_all_tasks():
    """Resume all paused tasks and the worker."""
    affected = Task.query.filter(Task.status == TaskStatus.PAUSED.value).update(
        {"status": TaskStatus.PENDING.value}, synchronize_session=False
    )
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.resume()

    logger.info("Resumed all %d paused tasks and worker", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/pause/sync")
def pause_sync_tasks():
    """Pause all pending sync tasks and stop the worker from picking up new syncs."""
    affected = Task.query.filter(
        Task.task_type == TaskType.SYNC.value, Task.status == TaskStatus.PENDING.value
    ).update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.pause("sync")

    logger.info("Paused all %d pending sync tasks", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/resume/sync")
def resume_sync_tasks():
    """Resume all paused sync tasks and the sync worker."""
    affected = Task.query.filter(
        Task.task_type == TaskType.SYNC.value, Task.status == TaskStatus.PAUSED.value
    ).update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.resume("sync")

    logger.info("Resumed all %d paused sync tasks", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/pause/download")
def pause_download_tasks():
    """Pause all pending download tasks and stop the worker from picking up new downloads."""
    affected = Task.query.filter(
        Task.task_type == TaskType.DOWNLOAD.value,
        Task.status == TaskStatus.PENDING.value,
    ).update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.pause("download")

    logger.info("Paused all %d pending download tasks", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/resume/download")
def resume_download_tasks():
    """Resume all paused download tasks and the download worker."""
    affected = Task.query.filter(
        Task.task_type == TaskType.DOWNLOAD.value,
        Task.status == TaskStatus.PAUSED.value,
    ).update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    db.session.commit()

    worker = get_worker()
    if worker:
        worker.resume("download")

    logger.info("Resumed all %d paused download tasks", affected)
    return jsonify({"affected": affected, "skipped": 0})


@bp.post("/cancel/all")
def cancel_all_tasks():
    """Cancel all pending and paused tasks."""
    affected = Task.query.filter(
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.PAUSED.value])
    ).update(
        {"status": TaskStatus.CANCELLED.value, "completed_at": db.func.now()},
        synchronize_session=False,
    )
    db.session.commit()

    logger.info("Cancelled all %d pending/paused tasks", affected)
    return jsonify({"affected": affected, "skipped": 0})
