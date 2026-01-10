from flask import jsonify
from flask_openapi3 import APIBlueprint, Tag

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Video, VideoList
from app.schemas.videos import VideoListPath, VideoPath, VideoQuery
from app.services import HistoryService

logger = get_logger("routes.videos")
tag = Tag(name="Videos", description="Video management")
bp = APIBlueprint("videos", __name__, url_prefix="/api/videos", abp_tags=[tag])


@bp.get("/")
def list_videos(query: VideoQuery):
    """List videos with optional filtering."""
    q = Video.query

    if query.list_id:
        q = q.filter_by(list_id=query.list_id)
    if query.downloaded is not None:
        q = q.filter_by(downloaded=query.downloaded)

    offset = (query.page - 1) * query.per_page
    videos = (
        q.order_by(Video.created_at.desc()).offset(offset).limit(query.per_page).all()
    )
    return jsonify([v.to_dict() for v in videos])


@bp.get("/<int:video_id>")
def get_video(path: VideoPath):
    """Get a video by ID."""
    video = Video.query.get(path.video_id)
    if not video:
        raise NotFoundError("Video", path.video_id)
    return jsonify(video.to_dict())


@bp.get("/list/<int:list_id>")
def get_videos_by_list(path: VideoListPath, query: VideoQuery):
    """Get all videos for a specific list."""
    video_list = VideoList.query.get(path.list_id)
    if not video_list:
        raise NotFoundError("VideoList", path.list_id)

    q = Video.query.filter_by(list_id=path.list_id)

    if query.downloaded is not None:
        q = q.filter_by(downloaded=query.downloaded)

    offset = (query.page - 1) * query.per_page
    videos = (
        q.order_by(Video.created_at.desc()).offset(offset).limit(query.per_page).all()
    )
    return jsonify([v.to_dict() for v in videos])


@bp.post("/<int:video_id>/retry")
def retry_video(path: VideoPath):
    """Mark a video for retry."""
    video = Video.query.get(path.video_id)
    if not video:
        raise NotFoundError("Video", path.video_id)

    if video.downloaded:
        raise ValidationError("Video already downloaded")

    video.error_message = None
    video.retry_count += 1
    db.session.commit()

    HistoryService.log(
        HistoryAction.VIDEO_RETRY,
        "video",
        video.id,
        {"title": video.title, "retry_count": video.retry_count},
    )

    logger.info("Video %d marked for retry", path.video_id)
    return jsonify({"message": "Video queued for retry", "video": video.to_dict()})
