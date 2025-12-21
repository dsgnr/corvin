from flask import Blueprint, jsonify, request

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Video
from app.services import HistoryService

logger = get_logger("routes.videos")
bp = Blueprint("videos", __name__, url_prefix="/api/videos")


@bp.get("/")
def list_videos():
    """List videos with optional filtering."""
    list_id = request.args.get("list_id", type=int)
    downloaded = request.args.get("downloaded")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    query = Video.query

    if list_id:
        query = query.filter_by(list_id=list_id)
    if downloaded is not None:
        query = query.filter_by(downloaded=downloaded.lower() == "true")

    videos = query.order_by(Video.created_at.desc()).offset(offset).limit(limit).all()
    return jsonify([v.to_dict() for v in videos])


@bp.get("/<int:video_id>")
def get_video(video_id: int):
    """Get a video by ID."""
    video = Video.query.get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)
    return jsonify(video.to_dict())


@bp.get("/list/<int:list_id>")
def get_videos_by_list(list_id: int):
    """Get all videos for a specific list."""
    from app.models import VideoList

    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    downloaded = request.args.get("downloaded")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    query = Video.query.filter_by(list_id=list_id)

    if downloaded is not None:
        query = query.filter_by(downloaded=downloaded.lower() == "true")

    videos = query.order_by(Video.created_at.desc()).offset(offset).limit(limit).all()
    return jsonify([v.to_dict() for v in videos])


@bp.post("/<int:video_id>/retry")
def retry_video(video_id: int):
    """Mark a video for retry."""
    video = Video.query.get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)

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

    logger.info("Video %d marked for retry", video_id)
    return jsonify({"message": "Video queued for retry", "video": video.to_dict()})
