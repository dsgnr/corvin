import json
import time

from flask import Response, current_app, jsonify, request
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import func

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
    """Get fingerprint for change detection.

    Uses video count + max updated_at as a lightweight change indicator.
    """
    video_stats = (
        db.session.query(func.count(Video.id), func.max(Video.updated_at))
        .filter(Video.list_id == list_id)
        .first()
    )
    # Also check active task count to detect when downloads complete
    active_task_count = (
        db.session.query(func.count(Task.id))
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
    result = {
        "sync": {"pending": [], "running": []},
        "download": {"pending": [], "running": []},
    }

    # Get sync tasks for this list (usually 0-1)
    sync_tasks = (
        db.session.query(Task.status, Task.entity_id)
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

    # Get all active download tasks (usually a small number)
    # Then filter in Python - faster than subquery for SQLite
    download_tasks = (
        db.session.query(Task.status, Task.entity_id)
        .filter(
            Task.task_type == TaskType.DOWNLOAD.value,
            Task.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )

    if download_tasks:
        # Get video IDs for this list to filter download tasks
        video_ids = {
            v[0]
            for v in db.session.query(Video.id).filter(Video.list_id == list_id).all()
        }

        for status, entity_id in download_tasks:
            if entity_id in video_ids and status in result["download"]:
                result["download"][status].append(entity_id)

    return result


def _get_videos_for_stream(list_id: int, since: str | None = None) -> list[dict]:
    """Get video data optimised for SSE stream (minimal fields for display)."""
    from datetime import datetime

    q = db.session.query(
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
            pass  # Invalid timestamp, return all

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

    # SSE stream with incremental updates
    app = current_app._get_current_object()
    list_id = path.list_id

    def generate():
        last_fingerprint = None
        last_update_time = None
        heartbeat_counter = 0
        is_first_message = True

        while True:
            with app.app_context():
                fingerprint = _get_list_fingerprint(list_id)

                if fingerprint != last_fingerprint:
                    if is_first_message:
                        # First message: send full list
                        videos = _get_videos_for_stream(list_id)
                        is_first_message = False
                    else:
                        # Subsequent messages: only send changed videos
                        videos = _get_videos_for_stream(list_id, since=last_update_time)

                    # Track the current time for next incremental update
                    from datetime import datetime

                    last_update_time = datetime.utcnow().isoformat()

                    data = {
                        "type": "full" if len(videos) > 100 else "incremental",
                        "videos": videos,
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
