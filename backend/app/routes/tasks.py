import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import SessionLocal, get_db
from app.models.task import Task, TaskLog, TaskStatus, TaskType
from app.models.video import Video
from app.schemas.tasks import BulkDownloadRequest, BulkSyncRequest, BulkTaskIdsRequest
from app.task_queue import get_worker
from app.tasks import enqueue_task, schedule_downloads, schedule_syncs

logger = get_logger("routes.tasks")
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _get_tasks_fingerprint(
    task_type: str | None, status_filter: str | None, limit: int | None
) -> str:
    """Get fingerprint for change detection based on task statuses."""
    with SessionLocal() as db:
        q = db.query(Task).order_by(Task.created_at.desc())
        if task_type:
            q = q.filter_by(task_type=task_type)
        if status_filter:
            q = q.filter_by(status=status_filter)
        if limit:
            q = q.limit(limit)
        tasks = q.with_entities(Task.id, Task.status).all()
        return ",".join(f"{t.id}:{t.status}" for t in tasks)


def _get_tasks_for_stream(
    task_type: str | None, status_filter: str | None, limit: int | None
) -> list[dict]:
    """Get task data optimised for SSE stream."""
    with SessionLocal() as db:
        q = db.query(Task).order_by(Task.created_at.desc())
        if task_type:
            q = q.filter_by(task_type=task_type)
        if status_filter:
            q = q.filter_by(status=status_filter)
        if limit:
            q = q.limit(limit)
        tasks = q.all()
        entity_names = Task.batch_get_entity_names(db, tasks)
        return [t.to_dict(entity_name=entity_names.get(t.id)) for t in tasks]


def _get_stats_counts(db) -> dict:
    """Get all task stats in a single query using conditional aggregation."""
    result = (
        db.query(
            func.sum(
                case(
                    (
                        (Task.task_type == TaskType.SYNC.value)
                        & (Task.status == TaskStatus.PENDING.value),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_sync"),
            func.sum(
                case(
                    (
                        (Task.task_type == TaskType.DOWNLOAD.value)
                        & (Task.status == TaskStatus.PENDING.value),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_download"),
            func.sum(
                case(
                    (
                        (Task.task_type == TaskType.SYNC.value)
                        & (Task.status == TaskStatus.RUNNING.value),
                        1,
                    ),
                    else_=0,
                )
            ).label("running_sync"),
            func.sum(
                case(
                    (
                        (Task.task_type == TaskType.DOWNLOAD.value)
                        & (Task.status == TaskStatus.RUNNING.value),
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


@router.get("/")
async def list_tasks(
    request: Request,
    type: str | None = Query(None),
    status: str | None = Query(None, alias="status"),
    limit: int | None = Query(None),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List tasks with optional filtering. Supports SSE streaming."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        q = db.query(Task).order_by(Task.created_at.desc())
        if type:
            q = q.filter_by(task_type=type)
        if status:
            q = q.filter_by(status=status)
        q = q.offset(offset)
        if limit:
            q = q.limit(limit)
        tasks = q.all()
        entity_names = Task.batch_get_entity_names(db, tasks)
        return [t.to_dict(entity_name=entity_names.get(t.id)) for t in tasks]

    # SSE stream
    async def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            fingerprint = _get_tasks_fingerprint(type, status, limit)

            if fingerprint != last_fingerprint:
                data = _get_tasks_for_stream(type, status, limit)
                yield {"data": json.dumps(data, default=str)}
                last_fingerprint = fingerprint
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= 30:
                    yield {"comment": "heartbeat"}
                    heartbeat_counter = 0

            await asyncio.sleep(1)

    return EventSourceResponse(generate())


@router.get("/stats")
async def task_stats(request: Request, db: Session = Depends(get_db)):
    """Get task queue statistics. Supports SSE streaming."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        stats = _get_stats_counts(db)
        worker = get_worker()
        if worker:
            stats["worker"] = worker.get_stats()
        return stats

    # SSE stream
    async def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with SessionLocal() as db_session:
                counts = _get_stats_counts(db_session)
            worker = get_worker()
            worker_stats = worker.get_stats() if worker else {}
            fingerprint = (
                tuple(counts.values()),
                worker_stats.get("paused"),
                worker_stats.get("sync_paused"),
                worker_stats.get("download_paused"),
            )

            if fingerprint != last_fingerprint:
                if worker:
                    counts["worker"] = worker_stats
                yield {"data": json.dumps(counts, default=str)}
                last_fingerprint = fingerprint
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= 30:
                    yield {"comment": "heartbeat"}
                    heartbeat_counter = 0

            await asyncio.sleep(1)

    return EventSourceResponse(generate())


@router.get("/active")
def get_active_tasks(
    list_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get all pending and running tasks, grouped by type and status."""
    active_statuses = [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]

    result = {
        "sync": {"pending": [], "running": []},
        "download": {"pending": [], "running": []},
    }

    if list_id:
        sync_tasks = (
            db.query(Task.status, Task.entity_id)
            .filter(
                Task.task_type == TaskType.SYNC.value,
                Task.status.in_(active_statuses),
                Task.entity_id == list_id,
            )
            .all()
        )

        for task_status, entity_id in sync_tasks:
            if task_status in result["sync"]:
                result["sync"][task_status].append(entity_id)

        download_tasks = (
            db.query(Task.status, Task.entity_id)
            .filter(
                Task.task_type == TaskType.DOWNLOAD.value,
                Task.status.in_(active_statuses),
            )
            .all()
        )

        if download_tasks:
            video_ids = {
                v[0] for v in db.query(Video.id).filter(Video.list_id == list_id).all()
            }

            for task_status, entity_id in download_tasks:
                if entity_id in video_ids and task_status in result["download"]:
                    result["download"][task_status].append(entity_id)
    else:
        tasks = (
            db.query(Task.task_type, Task.status, Task.entity_id)
            .filter(Task.status.in_(active_statuses))
            .all()
        )

        for task_type, task_status, entity_id in tasks:
            if task_type in result and task_status in result[task_type]:
                result[task_type][task_status].append(entity_id)

    return result


@router.get("/{task_id}")
def get_task(
    task_id: int,
    include_logs: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Get a task by ID with optional logs."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    return task.to_dict(include_logs=include_logs)


@router.get("/{task_id}/logs")
def get_task_logs(task_id: int, db: Session = Depends(get_db)):
    """Get logs for a specific task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

    logs = task.logs.order_by(TaskLog.created_at.asc()).all()
    return [log.to_dict() for log in logs]


@router.post("/sync/list/{list_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_list_sync(list_id: int):
    """Trigger a sync for a specific list."""
    task = enqueue_task(TaskType.SYNC.value, list_id)

    if not task:
        raise ConflictError("List sync already queued or running")

    logger.info("Triggered sync for list %d", list_id)
    return task.to_dict()


@router.post("/sync/lists", status_code=status.HTTP_202_ACCEPTED)
def trigger_lists_sync(body: BulkSyncRequest):
    """Trigger sync for multiple lists by ID."""
    result = schedule_syncs(body.list_ids)
    logger.info(
        "Triggered sync for %d lists: %d queued", len(body.list_ids), result["queued"]
    )
    return {"queued": result["queued"], "skipped": result["skipped"]}


@router.post("/sync/all", status_code=status.HTTP_202_ACCEPTED)
def trigger_all_syncs():
    """Trigger sync for all enabled lists."""
    result = schedule_syncs(force=True)
    logger.info("Force triggered a sync for all lists: %d queued", result["queued"])
    return {"queued": result["queued"], "skipped": result["skipped"]}


@router.post("/download/video/{video_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_video_download(video_id: int):
    """Trigger download for a specific video."""
    task = enqueue_task(TaskType.DOWNLOAD.value, video_id)

    if not task:
        raise ConflictError("Video download already queued or running")

    logger.info("Triggered download for video %d", video_id)
    return task.to_dict()


@router.post("/download/videos", status_code=status.HTTP_202_ACCEPTED)
def trigger_videos_download(body: BulkDownloadRequest):
    """Trigger download for multiple videos by ID."""
    result = schedule_downloads(body.video_ids)
    logger.info(
        "Triggered download for %d videos: %d queued",
        len(body.video_ids),
        result["queued"],
    )
    return {"queued": result["queued"], "skipped": result["skipped"]}


@router.post("/download/pending", status_code=status.HTTP_202_ACCEPTED)
def trigger_pending_downloads():
    """Trigger download for all pending videos."""
    result = schedule_downloads()
    logger.info("Triggered pending downloads: %d queued", result["queued"])
    return {"queued": result["queued"], "skipped": result["skipped"]}


@router.post("/{task_id}/retry")
def retry_task(task_id: int, db: Session = Depends(get_db)):
    """Retry a failed or completed task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

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
    db.commit()

    worker = get_worker()
    if worker:
        worker.notify()

    logger.info("Task %d reset for retry", task_id)
    return task.to_dict()


@router.post("/{task_id}/pause")
def pause_task(task_id: int, db: Session = Depends(get_db)):
    """Pause a pending task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

    if task.status != TaskStatus.PENDING.value:
        raise ValidationError("Can only pause pending tasks")

    task.status = TaskStatus.PAUSED.value
    db.commit()

    logger.info("Task %d paused", task_id)
    return task.to_dict()


@router.post("/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db)):
    """Resume a paused task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

    if task.status != TaskStatus.PAUSED.value:
        raise ValidationError("Can only resume paused tasks")

    task.status = TaskStatus.PENDING.value
    db.commit()

    worker = get_worker()
    if worker:
        worker.notify()

    logger.info("Task %d resumed", task_id)
    return task.to_dict()


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    """Cancel a pending or paused task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise NotFoundError("Task", task_id)

    if task.status not in (TaskStatus.PENDING.value, TaskStatus.PAUSED.value):
        raise ValidationError("Can only cancel pending or paused tasks")

    task.status = TaskStatus.CANCELLED.value
    task.completed_at = func.now()
    db.commit()

    logger.info("Task %d cancelled", task_id)
    return task.to_dict()


@router.post("/pause")
def pause_tasks(body: BulkTaskIdsRequest, db: Session = Depends(get_db)):
    """Pause multiple pending tasks."""
    affected = (
        db.query(Task)
        .filter(Task.id.in_(body.task_ids), Task.status == TaskStatus.PENDING.value)
        .update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    )
    db.commit()

    skipped = len(body.task_ids) - affected
    logger.info("Paused %d tasks, skipped %d", affected, skipped)
    return {"affected": affected, "skipped": skipped}


@router.post("/resume")
def resume_tasks(body: BulkTaskIdsRequest, db: Session = Depends(get_db)):
    """Resume multiple paused tasks."""
    affected = (
        db.query(Task)
        .filter(Task.id.in_(body.task_ids), Task.status == TaskStatus.PAUSED.value)
        .update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker and affected > 0:
        worker.notify()

    skipped = len(body.task_ids) - affected
    logger.info("Resumed %d tasks, skipped %d", affected, skipped)
    return {"affected": affected, "skipped": skipped}


@router.post("/cancel")
def cancel_tasks(body: BulkTaskIdsRequest, db: Session = Depends(get_db)):
    """Cancel multiple pending or paused tasks."""
    affected = (
        db.query(Task)
        .filter(
            Task.id.in_(body.task_ids),
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.PAUSED.value]),
        )
        .update(
            {"status": TaskStatus.CANCELLED.value, "completed_at": func.now()},
            synchronize_session=False,
        )
    )
    db.commit()

    skipped = len(body.task_ids) - affected
    logger.info("Cancelled %d tasks, skipped %d", affected, skipped)
    return {"affected": affected, "skipped": skipped}


@router.post("/pause/all")
def pause_all_tasks(db: Session = Depends(get_db)):
    """Pause all pending tasks and stop the worker from picking up new tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status == TaskStatus.PENDING.value)
        .update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.pause()

    logger.info("Paused all %d pending tasks and worker", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/resume/all")
def resume_all_tasks(db: Session = Depends(get_db)):
    """Resume all paused tasks and the worker."""
    affected = (
        db.query(Task)
        .filter(Task.status == TaskStatus.PAUSED.value)
        .update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.resume()

    logger.info("Resumed all %d paused tasks and worker", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/pause/sync")
def pause_sync_tasks(db: Session = Depends(get_db)):
    """Pause all pending sync tasks and stop the worker from picking up new syncs."""
    affected = (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.SYNC.value,
            Task.status == TaskStatus.PENDING.value,
        )
        .update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.pause("sync")

    logger.info("Paused all %d pending sync tasks", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/resume/sync")
def resume_sync_tasks(db: Session = Depends(get_db)):
    """Resume all paused sync tasks and the sync worker."""
    affected = (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.SYNC.value,
            Task.status == TaskStatus.PAUSED.value,
        )
        .update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.resume("sync")

    logger.info("Resumed all %d paused sync tasks", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/pause/download")
def pause_download_tasks(db: Session = Depends(get_db)):
    """Pause all pending download tasks and stop the worker from picking up new downloads."""
    affected = (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.DOWNLOAD.value,
            Task.status == TaskStatus.PENDING.value,
        )
        .update({"status": TaskStatus.PAUSED.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.pause("download")

    logger.info("Paused all %d pending download tasks", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/resume/download")
def resume_download_tasks(db: Session = Depends(get_db)):
    """Resume all paused download tasks and the download worker."""
    affected = (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.DOWNLOAD.value,
            Task.status == TaskStatus.PAUSED.value,
        )
        .update({"status": TaskStatus.PENDING.value}, synchronize_session=False)
    )
    db.commit()

    worker = get_worker()
    if worker:
        worker.resume("download")

    logger.info("Resumed all %d paused download tasks", affected)
    return {"affected": affected, "skipped": 0}


@router.post("/cancel/all")
def cancel_all_tasks(db: Session = Depends(get_db)):
    """Cancel all pending and paused tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.PAUSED.value]))
        .update(
            {"status": TaskStatus.CANCELLED.value, "completed_at": func.now()},
            synchronize_session=False,
        )
    )
    db.commit()

    logger.info("Cancelled all %d pending/paused tasks", affected)
    return {"affected": affected, "skipped": 0}
