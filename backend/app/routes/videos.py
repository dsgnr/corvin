import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import SessionLocal, get_db
from app.models import HistoryAction, Video, VideoList
from app.models.task import Task, TaskStatus, TaskType
from app.services import HistoryService

logger = get_logger("routes.videos")
router = APIRouter(prefix="/api/videos", tags=["Videos"])

ACTIVE_STATUSES = [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]


def _get_list_fingerprint(list_id: int) -> tuple:
    """Get fingerprint for change detection."""
    with SessionLocal() as db:
        video_stats = (
            db.query(func.count(Video.id), func.max(Video.updated_at))
            .filter(Video.list_id == list_id)
            .first()
        )
        active_task_count = (
            db.query(func.count(Task.id))
            .filter(Task.status.in_(ACTIVE_STATUSES))
            .scalar()
        )
        return (
            video_stats[0],
            str(video_stats[1]) if video_stats[1] else None,
            active_task_count,
        )


def _get_active_tasks_for_list(list_id: int) -> dict:
    """Get active task status for a specific list."""
    with SessionLocal() as db:
        result = {
            "sync": {"pending": [], "running": []},
            "download": {"pending": [], "running": []},
        }

        sync_tasks = (
            db.query(Task.status, Task.entity_id)
            .filter(
                Task.task_type == TaskType.SYNC.value,
                Task.status.in_(ACTIVE_STATUSES),
                Task.entity_id == list_id,
            )
            .all()
        )

        for status, entity_id in sync_tasks:
            if status in result["sync"]:
                result["sync"][status].append(entity_id)

        download_tasks = (
            db.query(Task.status, Task.entity_id)
            .filter(
                Task.task_type == TaskType.DOWNLOAD.value,
                Task.status.in_(ACTIVE_STATUSES),
            )
            .all()
        )

        if download_tasks:
            video_ids = {
                v[0] for v in db.query(Video.id).filter(Video.list_id == list_id).all()
            }

            for status, entity_id in download_tasks:
                if entity_id in video_ids and status in result["download"]:
                    result["download"][status].append(entity_id)

        return result


def _get_videos_for_stream(list_id: int, since: str | None = None) -> list[dict]:
    """Get video data optimised for SSE stream."""
    with SessionLocal() as db:
        q = db.query(
            Video.id,
            Video.title,
            Video.thumbnail,
            Video.media_type,
            Video.duration,
            Video.upload_date,
            Video.downloaded,
            Video.error_message,
            Video.created_at,
        ).filter(Video.list_id == list_id)

        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                q = q.filter(Video.updated_at > since_dt)
            except ValueError:
                pass

        videos = q.order_by(Video.created_at.desc()).all()

        result = []
        for v in videos:
            result.append(
                {
                    "id": v[0],
                    "title": v[1],
                    "thumbnail": v[2],
                    "media_type": v[3],
                    "duration": v[4],
                    "upload_date": v[5].isoformat() if v[5] else None,
                    "downloaded": v[6],
                    "error_message": v[7],
                    "created_at": v[8].isoformat() if v[8] else None,
                }
            )
        return result


@router.get("/")
def list_videos(
    list_id: int | None = Query(None),
    downloaded: bool | None = Query(None),
    limit: int | None = Query(None),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List videos with optional filtering."""
    q = db.query(Video)

    if list_id:
        q = q.filter_by(list_id=list_id)
    if downloaded is not None:
        q = q.filter_by(downloaded=downloaded)

    q = q.order_by(Video.created_at.desc()).offset(offset)
    if limit:
        q = q.limit(limit)
    return [v.to_dict() for v in q.all()]


@router.get("/list/{list_id}")
async def get_videos_by_list(
    list_id: int,
    request: Request,
    downloaded: bool | None = Query(None),
    limit: int | None = Query(None),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """Get all videos for a specific list. Supports SSE streaming."""
    video_list = db.query(VideoList).get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        q = db.query(Video).filter_by(list_id=list_id)

        if downloaded is not None:
            q = q.filter_by(downloaded=downloaded)

        q = q.order_by(Video.created_at.desc()).offset(offset)
        if limit:
            q = q.limit(limit)
        return [v.to_dict() for v in q.all()]

    # SSE stream with incremental updates
    async def generate():
        last_fingerprint = None
        last_update_time = None
        heartbeat_counter = 0
        is_first_message = True

        while True:
            fingerprint = _get_list_fingerprint(list_id)

            if fingerprint != last_fingerprint:
                if is_first_message:
                    videos = _get_videos_for_stream(list_id)
                    is_first_message = False
                else:
                    videos = _get_videos_for_stream(list_id, since=last_update_time)

                last_update_time = datetime.utcnow().isoformat()

                data = {
                    "type": "full" if len(videos) > 100 else "incremental",
                    "videos": videos,
                    "tasks": _get_active_tasks_for_list(list_id),
                }
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


@router.get("/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get a video by ID."""
    video = db.query(Video).get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)
    return video.to_dict()


@router.post("/{video_id}/retry")
def retry_video(video_id: int, db: Session = Depends(get_db)):
    """Mark a video for retry."""
    video = db.query(Video).get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)

    if video.downloaded:
        raise ValidationError("Video already downloaded")

    video.error_message = None
    video.retry_count += 1
    db.commit()

    HistoryService.log(
        db,
        HistoryAction.VIDEO_RETRY,
        "video",
        video.id,
        {"title": video.title, "retry_count": video.retry_count},
    )

    logger.info("Video %d marked for retry", video_id)
    return {"message": "Video queued for retry", "video": video.to_dict()}
