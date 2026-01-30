"""
Tasks routes.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, literal_column
from sqlalchemy.orm import Session, aliased
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.helpers import calculate_total_pages
from app.core.logging import get_logger
from app.extensions import ReadSessionLocal, get_db, sse_executor
from app.models.task import Task, TaskStatus, TaskType
from app.models.video import Video
from app.models.video_list import VideoList
from app.schemas.common import AffectedResponse, PausedResponse
from app.schemas.tasks import (
    BulkResultResponse,
    TaskResponse,
    TasksPaginatedResponse,
    TaskStatsResponse,
)
from app.sse_hub import Channel, broadcast, hub
from app.sse_stream import sse_cors_headers, sse_response, wants_sse
from app.task_queue import get_worker
from app.tasks import enqueue_task, schedule_downloads, schedule_syncs

logger = get_logger("routes.tasks")
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

ACTIVE_TASK_STATUSES = (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)


def _fetch_tasks_paginated(
    task_type: str | None,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    """Fetch paginated tasks."""
    with ReadSessionLocal() as db:
        vl = aliased(VideoList)
        v = aliased(Video)

        query = (
            db.query(
                Task.id,
                Task.task_type,
                Task.status,
                Task.entity_id,
                Task.created_at,
                Task.started_at,
                Task.completed_at,
                Task.error,
                Task.result,
                Task.retry_count,
                Task.max_retries,
                case(
                    (Task.task_type == TaskType.SYNC.value, vl.name),
                    (Task.task_type == TaskType.DOWNLOAD.value, v.title),
                    else_=literal_column("NULL"),
                ).label("entity_name"),
            )
            .outerjoin(
                vl,
                (Task.task_type == TaskType.SYNC.value) & (Task.entity_id == vl.id),
            )
            .outerjoin(
                v,
                (Task.task_type == TaskType.DOWNLOAD.value) & (Task.entity_id == v.id),
            )
        )

        if task_type:
            query = query.filter(Task.task_type == task_type)
        if status:
            # Map 'queued' filter to 'pending' status
            # Map 'active' filter to pending OR running
            if status == "queued":
                query = query.filter(Task.status == "pending")
            elif status == "active":
                query = query.filter(Task.status.in_(ACTIVE_TASK_STATUSES))
            else:
                query = query.filter(Task.status == status)
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                Task.task_type.ilike(search_pattern)
                | Task.status.ilike(search_pattern)
                | vl.name.ilike(search_pattern)
                | v.title.ilike(search_pattern)
            )

        # Get total count
        count_query = db.query(func.count(Task.id))
        if task_type:
            count_query = count_query.filter(Task.task_type == task_type)
        if status:
            if status == "queued":
                count_query = count_query.filter(Task.status == "pending")
            elif status == "active":
                count_query = count_query.filter(Task.status.in_(ACTIVE_TASK_STATUSES))
            else:
                count_query = count_query.filter(Task.status == status)
        if search:
            search_pattern = f"%{search}%"
            vl2 = aliased(VideoList)
            v2 = aliased(Video)
            count_query = (
                count_query.outerjoin(
                    vl2,
                    (Task.task_type == TaskType.SYNC.value)
                    & (Task.entity_id == vl2.id),
                )
                .outerjoin(
                    v2,
                    (Task.task_type == TaskType.DOWNLOAD.value)
                    & (Task.entity_id == v2.id),
                )
                .filter(
                    Task.task_type.ilike(search_pattern)
                    | Task.status.ilike(search_pattern)
                    | vl2.name.ilike(search_pattern)
                    | v2.title.ilike(search_pattern)
                )
            )

        total = count_query.scalar() or 0
        total_pages = calculate_total_pages(total, page_size)

        rows = (
            query.order_by(Task.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "tasks": [Task.row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


def _fetch_task_counts(db: Session) -> dict:
    """Aggregate pending/running counts by type."""
    counts = db.query(
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
    ).one()

    return {
        "pending_sync": counts.pending_sync or 0,
        "pending_download": counts.pending_download or 0,
        "running_sync": counts.running_sync or 0,
        "running_download": counts.running_download or 0,
    }


@router.get("", response_model=TasksPaginatedResponse)
async def list_tasks(
    request: Request,
    task_type: str | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List paginated tasks or stream updates via SSE."""
    if not wants_sse(request):
        return _fetch_tasks_paginated(task_type, status_filter, search, page, page_size)

    return sse_response(
        request,
        Channel.TASKS,
        lambda: _fetch_tasks_paginated(
            task_type, status_filter, search, page, page_size
        ),
    )


@router.get("/stats", response_model=TaskStatsResponse)
async def task_stats(request: Request):
    """Return queue statistics or stream via SSE."""
    if not wants_sse(request):
        with ReadSessionLocal() as db:
            stats = _fetch_task_counts(db)
            worker = get_worker()
            if worker:
                stats["worker"] = worker.get_stats()
            # Check if downloads are paused due to schedule
            from app.models.download_schedule import DownloadSchedule

            stats["schedule_paused"] = not DownloadSchedule.is_download_allowed(db)
            return stats

    async def stream():
        """SSE stream for task statistics updates."""
        event_loop = asyncio.get_running_loop()
        heartbeat_interval = 30

        def fetch_stats():
            with ReadSessionLocal() as db:
                stats = _fetch_task_counts(db)
                worker = get_worker()
                if worker:
                    stats["worker"] = worker.get_stats()
                # Check if downloads are paused due to schedule
                from app.models.download_schedule import DownloadSchedule

                stats["schedule_paused"] = not DownloadSchedule.is_download_allowed(db)
                return stats

        # Send initial data immediately
        stats = await event_loop.run_in_executor(sse_executor, fetch_stats)
        yield {"data": json.dumps(stats, default=str)}

        async with hub.subscribe(Channel.TASKS_STATS) as notification_queue:
            while True:
                try:
                    await asyncio.wait_for(
                        notification_queue.get(), timeout=heartbeat_interval
                    )
                    # Received notification - fetch and send fresh data
                    stats = await event_loop.run_in_executor(sse_executor, fetch_stats)
                    yield {"data": json.dumps(stats, default=str)}
                except TimeoutError:
                    yield {"comment": "heartbeat"}

    return EventSourceResponse(stream(), headers=sse_cors_headers(request))


@router.post("/sync/list/{list_id}", status_code=202, response_model=TaskResponse)
def trigger_list_sync(list_id: int):
    """Trigger sync for a specific list."""
    task = enqueue_task(TaskType.SYNC.value, list_id)
    if not task:
        raise ConflictError("List sync already queued or running")
    logger.info("Triggered sync for list %d", list_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS, Channel.list_tasks(list_id))
    return task.to_dict()


@router.post("/sync/all", status_code=202, response_model=BulkResultResponse)
def trigger_all_syncs():
    """Force trigger a sync for all enabled lists."""
    result = schedule_syncs(force=True)
    logger.info("Triggered sync for all lists: %d queued", result["queued"])
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    return {"queued": result["queued"], "skipped": result["skipped"]}


@router.post("/download/video/{video_id}", status_code=202, response_model=TaskResponse)
def trigger_video_download(video_id: int):
    """Trigger download for a specific video."""
    task = enqueue_task(TaskType.DOWNLOAD.value, video_id)
    if not task:
        raise ConflictError("Video download already queued or running")
    logger.info("Triggered download for video %d", video_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    return task.to_dict()


@router.post("/download/pending", status_code=202, response_model=BulkResultResponse)
def trigger_pending_downloads():
    """Trigger download for all pending videos."""
    result = schedule_downloads()
    logger.info("Triggered pending downloads: %d queued", result["queued"])
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    return {"queued": result["queued"], "skipped": result["skipped"]}


def _notify_if_changed(affected: int):
    if affected > 0:
        broadcast(Channel.TASKS, Channel.TASKS_STATS)
        # Wake up worker to pick up newly pending tasks
        worker = get_worker()
        if worker:
            worker.notify()


@router.post("/pause/all", response_model=AffectedResponse)
def pause_all_tasks(db: Session = Depends(get_db)):
    """Pause all pending tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status == TaskStatus.PENDING.value)
        .update({Task.status: TaskStatus.PAUSED.value})
    )
    db.commit()
    logger.info("Paused %d tasks", affected)
    _notify_if_changed(affected)
    return {"affected": affected}


@router.post("/resume/all", response_model=AffectedResponse)
def resume_all_tasks(db: Session = Depends(get_db)):
    """Resume all paused tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status == TaskStatus.PAUSED.value)
        .update({Task.status: TaskStatus.PENDING.value})
    )
    db.commit()
    logger.info("Resumed %d tasks", affected)
    _notify_if_changed(affected)
    return {"affected": affected}


@router.post("/cancel/all", response_model=AffectedResponse)
def cancel_all_tasks(db: Session = Depends(get_db)):
    """Cancel all pending/paused tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.PAUSED.value]))
        .update({Task.status: TaskStatus.CANCELLED.value})
    )
    db.commit()
    logger.info("Cancelled %d tasks", affected)
    _notify_if_changed(affected)
    return {"affected": affected}


@router.post("/retry/failed", response_model=AffectedResponse)
def retry_all_failed_tasks(db: Session = Depends(get_db)):
    """Retry all failed tasks."""
    affected = (
        db.query(Task)
        .filter(Task.status == TaskStatus.FAILED.value)
        .update(
            {
                Task.status: TaskStatus.PENDING.value,
                Task.error: None,
                Task.started_at: None,
                Task.completed_at: None,
                Task.retry_count: 0,
            }
        )
    )
    db.commit()
    logger.info("Retried %d failed tasks", affected)
    _notify_if_changed(affected)
    return {"affected": affected}


@router.post("/pause/sync", response_model=PausedResponse)
def pause_sync_tasks():
    worker = get_worker()
    if worker:
        worker.pause("sync")
    broadcast(Channel.TASKS_STATS)
    return {"affected": 1, "paused": True}


@router.post("/resume/sync", response_model=PausedResponse)
def resume_sync_tasks():
    worker = get_worker()
    if worker:
        worker.resume("sync")
    broadcast(Channel.TASKS_STATS)
    return {"affected": 1, "paused": False}


@router.post("/pause/download", response_model=PausedResponse)
def pause_download_tasks():
    worker = get_worker()
    if worker:
        worker.pause("download")
    broadcast(Channel.TASKS_STATS)
    return {"affected": 1, "paused": True}


@router.post("/resume/download", response_model=PausedResponse)
def resume_download_tasks():
    worker = get_worker()
    if worker:
        worker.resume("download")
    broadcast(Channel.TASKS_STATS)
    return {"affected": 1, "paused": False}


@router.post("/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: int, db: Session = Depends(get_db)):
    """Retry a failed, completed, or cancelled task."""
    task = db.get(Task, task_id)
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
    logger.info("Task %d reset for retry", task_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    # Wake up worker to pick up the task
    worker = get_worker()
    if worker:
        worker.notify()
    return task.to_dict()


@router.post("/{task_id}/pause", response_model=TaskResponse)
def pause_task(task_id: int, db: Session = Depends(get_db)):
    """Pause a pending task."""
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    if task.status != TaskStatus.PENDING.value:
        raise ValidationError("Can only pause pending tasks")

    task.status = TaskStatus.PAUSED.value
    db.commit()
    logger.info("Task %d paused", task_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    return task.to_dict()


@router.post("/{task_id}/resume", response_model=TaskResponse)
def resume_task(task_id: int, db: Session = Depends(get_db)):
    """Resume a paused task."""
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    if task.status != TaskStatus.PAUSED.value:
        raise ValidationError("Can only resume paused tasks")

    task.status = TaskStatus.PENDING.value
    db.commit()
    logger.info("Task %d resumed", task_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    # Wake up worker to pick up the task
    worker = get_worker()
    if worker:
        worker.notify()
    return task.to_dict()


@router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    """Cancel a pending or paused task."""
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    if task.status not in (TaskStatus.PENDING.value, TaskStatus.PAUSED.value):
        raise ValidationError("Can only cancel pending or paused tasks")

    task.status = TaskStatus.CANCELLED.value
    db.commit()
    logger.info("Task %d cancelled", task_id)
    broadcast(Channel.TASKS, Channel.TASKS_STATS)
    return task.to_dict()
