"""
Videos routes.
"""

import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.helpers import calculate_total_pages
from app.core.logging import get_logger
from app.extensions import ReadSessionLocal, get_db, sse_executor
from app.models import HistoryAction, Video
from app.models.task import Task, TaskType
from app.schemas.tasks import TasksPaginatedResponse
from app.schemas.videos import VideoRetryResponse, VideoWithListResponse
from app.services import HistoryService, progress_service
from app.sse_hub import Channel, broadcast
from app.tasks import enqueue_task

logger = get_logger("routes.videos")
router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.get("/{video_id}", response_model=VideoWithListResponse)
async def get_video(video_id: int):
    """Get a single video by ID."""

    def fetch():
        with ReadSessionLocal() as db:
            v = db.get(Video, video_id)
            if not v:
                return None
            result = v.to_dict()
            result["list"] = v.video_list.to_dict() if v.video_list else None
            return result

    result = await asyncio.get_event_loop().run_in_executor(sse_executor, fetch)
    if result is None:
        raise NotFoundError("Video", video_id)
    return result


@router.post("/{video_id}/retry", response_model=VideoRetryResponse)
def retry_video(video_id: int, db: Session = Depends(get_db)):
    """Mark a failed video for retry."""
    video = db.get(Video, video_id)
    if not video:
        raise NotFoundError("Video", video_id)
    if video.downloaded:
        raise ValidationError("Video already downloaded")

    video.error_message = None
    video.retry_count += 1
    db.commit()

    # Clear any stale progress/error state
    progress_service.clear(video_id)

    # Queue the download
    task = enqueue_task(TaskType.DOWNLOAD.value, video_id)
    if not task:
        raise ConflictError("Video download already queued or running")

    broadcast(Channel.TASKS, Channel.TASKS_STATS)

    HistoryService.log(
        db,
        HistoryAction.VIDEO_RETRY,
        "video",
        video.id,
        {"title": video.title, "retry_count": video.retry_count},
    )

    logger.info("Video %d queued for retry", video_id)
    return {"message": "Video queued for retry", "video": video.to_dict()}


@router.post("/{video_id}/blacklist", response_model=VideoWithListResponse)
def toggle_blacklist(video_id: int, db: Session = Depends(get_db)):
    """Toggle the blacklist status of a video."""
    video = db.get(Video, video_id)
    if not video:
        raise NotFoundError("Video", video_id)

    video.blacklisted = not video.blacklisted
    db.commit()

    action = "blacklisted" if video.blacklisted else "unblacklisted"
    logger.info("Video %d %s", video_id, action)

    # Notify SSE subscribers
    broadcast(Channel.list_videos(video.list_id))

    result = video.to_dict()
    result["list"] = video.video_list.to_dict() if video.video_list else None
    return result


def _fetch_video_tasks(video_id: int, page: int, page_size: int) -> dict:
    """Fetch paginated tasks for a specific video."""
    with ReadSessionLocal() as db:
        # Query download tasks for this video
        query = db.query(Task).filter(
            Task.task_type == TaskType.DOWNLOAD.value, Task.entity_id == video_id
        )

        # Get total count
        total = query.count()
        total_pages = calculate_total_pages(total, page_size)

        # Apply pagination
        tasks = (
            query.order_by(Task.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "tasks": [task.to_dict() for task in tasks],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


@router.get("/{video_id}/tasks", response_model=TasksPaginatedResponse)
async def get_video_tasks(
    video_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Get paginated tasks for a specific video."""
    return _fetch_video_tasks(video_id, page, page_size)
