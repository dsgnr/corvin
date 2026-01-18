"""
Videos routes.
"""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import ReadSessionLocal, get_db, sse_executor
from app.models import HistoryAction, Video
from app.schemas.videos import VideoRetryResponse, VideoWithListResponse
from app.services import HistoryService

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

    HistoryService.log(
        db,
        HistoryAction.VIDEO_RETRY,
        "video",
        video.id,
        {"title": video.title, "retry_count": video.retry_count},
    )

    logger.info("Video %d marked for retry", video_id)
    return {"message": "Video queued for retry", "video": video.to_dict()}


@router.post("/{video_id}/blacklist", response_model=VideoWithListResponse)
def toggle_blacklist(video_id: int, db: Session = Depends(get_db)):
    """Toggle the blacklist status of a video."""
    from app.sse_hub import Channel, notify

    video = db.get(Video, video_id)
    if not video:
        raise NotFoundError("Video", video_id)

    video.blacklisted = not video.blacklisted
    db.commit()

    action = "blacklisted" if video.blacklisted else "unblacklisted"
    logger.info("Video %d %s", video_id, action)

    # Notify SSE subscribers
    notify(Channel.list_videos(video.list_id))

    result = video.to_dict()
    result["list"] = video.video_list.to_dict() if video.video_list else None
    return result
