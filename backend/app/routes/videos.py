import json
import time

from flask import Response, current_app, jsonify, request
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import func, select

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Video, VideoList
from app.models.task import Task, TaskStatus, TaskType
from app.schemas.videos import VideoListPath, VideoPath, VideoQuery
from app.services import HistoryService

logger = get_logger("routes.videos")
tag = Tag(name="Videos", description="Video management")
bp = APIBlueprint("videos", __name__, url_prefix="/api/videos", abp_tags=[tag])

ACTIVE_STATUSES = [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]


def _get_list_fingerprint(list_id: int) -> tuple:
    """Get combined fingerprint from videos and tasks for change detection."""
    video_stats = (
        db.session.query(func.count(Video.id), func.max(Video.updated_at))
        .filter(Video.list_id == list_id)
        .first()
    )
    task_stats = (
        db.session.query(func.count(Task.id), func.max(Task.started_at))
        .filter(Task.status.in_(ACTIVE_STATUSES))
        .first()
    )
    return (
        video_stats[0],
        str(video_stats[1]) if video_stats[1] else None,
        task_stats[0],
        str(task_stats[1]) if task_stats[1] else None,
    )


def _get_active_tasks_for_list(list_id: int) -> dict:
    """Get active task status for a specific list."""
    result = {
        "sync": {"pending": [], "running": []},
        "download": {"pending": [], "running": []},
    }

    video_ids_subq = select(Video.id).where(Video.list_id == list_id)

    tasks = (
        db.session.query(Task.task_type, Task.status, Task.entity_id)
        .filter(Task.status.in_(ACTIVE_STATUSES))
        .filter(
            db.or_(
                db.and_(
                    Task.task_type == TaskType.SYNC.value,
                    Task.entity_id == list_id,
                ),
                db.and_(
                    Task.task_type == TaskType.DOWNLOAD.value,
                    Task.entity_id.in_(video_ids_subq),
                ),
            )
        )
        .all()
    )

    for task_type, status, entity_id in tasks:
        if task_type in result and status in result[task_type]:
            result[task_type][status].append(entity_id)

    return result


def _get_videos_for_stream(list_id: int) -> list[dict]:
    """Get video data optimized for SSE stream (minimal fields)."""
    videos = (
        db.session.query(
            Video.id,
            Video.title,
            Video.thumbnail,
            Video.media_type,
            Video.duration,
            Video.upload_date,
            Video.downloaded,
            Video.error_message,
            Video.labels,
        )
        .filter(Video.list_id == list_id)
        .order_by(Video.created_at.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "title": v.title,
            "thumbnail": v.thumbnail,
            "media_type": v.media_type,
            "duration": v.duration,
            "upload_date": v.upload_date.isoformat() if v.upload_date else None,
            "downloaded": v.downloaded,
            "error_message": v.error_message,
            "labels": v.labels or {},
        }
        for v in videos
    ]


@bp.get("/")
def list_videos(query: VideoQuery):
    """List videos with optional filtering."""
    q = Video.query

    if query.list_id:
        q = q.filter_by(list_id=query.list_id)
    if query.downloaded is not None:
        q = q.filter_by(downloaded=query.downloaded)

    q = q.order_by(Video.created_at.desc()).offset(query.offset)
    if query.limit:
        q = q.limit(query.limit)
    return jsonify([v.to_dict() for v in q.all()])


@bp.get("/<int:video_id>")
def get_video(path: VideoPath):
    """Get a video by ID."""
    video = Video.query.get(path.video_id)
    if not video:
        raise NotFoundError("Video", path.video_id)
    return jsonify(video.to_dict())


@bp.get("/list/<int:list_id>")
def get_videos_by_list(path: VideoListPath, query: VideoQuery):
    """Get all videos for a specific list.

    If Accept header is 'text/event-stream', streams updates via SSE.
    Otherwise returns JSON array of videos.
    """
    video_list = VideoList.query.get(path.list_id)
    if not video_list:
        raise NotFoundError("VideoList", path.list_id)

    # Regular JSON response (early return)
    if request.accept_mimetypes.best != "text/event-stream":
        q = Video.query.filter_by(list_id=path.list_id)

        if query.downloaded is not None:
            q = q.filter_by(downloaded=query.downloaded)

        q = q.order_by(Video.created_at.desc()).offset(query.offset)
        if query.limit:
            q = q.limit(query.limit)
        return jsonify([v.to_dict() for v in q.all()])

    # SSE stream
    app = current_app._get_current_object()
    list_id = path.list_id

    def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with app.app_context():
                fingerprint = _get_list_fingerprint(list_id)

                if fingerprint != last_fingerprint:
                    data = {
                        "videos": _get_videos_for_stream(list_id),
                        "tasks": _get_active_tasks_for_list(list_id),
                    }
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
