import json
import time
from datetime import datetime

from flask import Response, current_app, jsonify, request
from flask_openapi3 import APIBlueprint, Tag

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Profile, VideoList
from app.models.history import History
from app.models.task import Task, TaskType
from app.models.video import Video
from app.schemas.lists import (
    ListCreate,
    ListPath,
    ListQuery,
    ListTasksQuery,
    ListUpdate,
)
from app.services import HistoryService
from app.services.ytdlp_service import YtDlpService
from app.tasks import enqueue_task

logger = get_logger("routes.lists")
tag = Tag(name="Lists", description="Video list management")
bp = APIBlueprint("lists", __name__, url_prefix="/api/lists", abp_tags=[tag])


@bp.post("/")
def create_list(body: ListCreate):
    """Create a new video list."""
    if not Profile.query.get(body.profile_id):
        raise NotFoundError("Profile", body.profile_id)

    if VideoList.query.filter_by(url=body.url).first():
        raise ConflictError("List with this URL already exists")

    from_date = _parse_from_date(body.from_date)

    metadata = {}
    try:
        metadata = YtDlpService.extract_list_metadata(body.url)
    except Exception as e:
        logger.warning("Failed to fetch metadata for %s: %s", body.url, e)

    video_list = VideoList(
        name=body.name,
        url=body.url,
        list_type=body.list_type,
        profile_id=body.profile_id,
        from_date=from_date,
        sync_frequency=body.sync_frequency,
        enabled=body.enabled,
        auto_download=body.auto_download,
        description=metadata.get("description"),
        thumbnail=metadata.get("thumbnail"),
        tags=",".join(metadata.get("tags", [])[:20]) if metadata.get("tags") else None,
        extractor=metadata.get("extractor"),
    )

    db.session.add(video_list)
    db.session.commit()

    thumbnails = metadata.get("thumbnails", [])
    if thumbnails and metadata.get("name"):
        artwork_dir = YtDlpService.DEFAULT_OUTPUT_DIR / metadata["name"]
        try:
            results = YtDlpService.download_list_artwork(thumbnails, artwork_dir)
            downloaded = [f for f, success in results.items() if success]
            if downloaded:
                logger.info(
                    "Downloaded artwork for %s: %s", video_list.name, downloaded
                )
            YtDlpService.write_channel_nfo(
                metadata, artwork_dir, metadata.get("channel_id")
            )
        except Exception as e:
            logger.warning("Failed to download artwork for %s: %s", video_list.name, e)

    HistoryService.log(
        HistoryAction.LIST_CREATED,
        "list",
        video_list.id,
        {"name": video_list.name, "url": video_list.url},
    )

    if video_list.enabled:
        enqueue_task(TaskType.SYNC.value, video_list.id)
        logger.info("Auto-triggered sync for new list: %s", video_list.name)

    logger.info("Created list: %s", video_list.name)
    return jsonify(video_list.to_dict()), 201


def _parse_from_date(date_str: str | None) -> str | None:
    """Validate and return from_date in YYYYMMDD format."""
    if not date_str:
        return None
    clean = date_str.replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValidationError("Invalid from_date format (use YYYYMMDD)")
    try:
        datetime.strptime(clean, "%Y%m%d")
    except ValueError as err:
        raise ValidationError("Invalid from_date (not a valid date)") from err
    return clean


@bp.get("/")
def list_all():
    """List all video lists."""
    lists = VideoList.query.all()
    return jsonify([vl.to_dict() for vl in lists])


@bp.get("/<int:list_id>")
def get_list(path: ListPath, query: ListQuery):
    """Get a video list by ID."""
    video_list = VideoList.query.get(path.list_id)
    if not video_list:
        raise NotFoundError("VideoList", path.list_id)
    data = video_list.to_dict(include_videos=query.include_videos)
    if query.include_stats:
        data["stats"] = video_list.get_video_stats()
    return jsonify(data)


@bp.put("/<int:list_id>")
def update_list(path: ListPath, body: ListUpdate):
    """Update a video list."""
    video_list = VideoList.query.get(path.list_id)
    if not video_list:
        raise NotFoundError("VideoList", path.list_id)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ValidationError("No data provided")

    if "profile_id" in data:
        if not Profile.query.get(data["profile_id"]):
            raise NotFoundError("Profile", data["profile_id"])

    if "url" in data and data["url"] != video_list.url:
        if VideoList.query.filter_by(url=data["url"]).first():
            raise ConflictError("List with this URL already exists")

    if "from_date" in data:
        data["from_date"] = _parse_from_date(data["from_date"])

    for field, value in data.items():
        setattr(video_list, field, value)

    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_UPDATED,
        "list",
        video_list.id,
        {"updated_fields": list(data.keys())},
    )

    logger.info("Updated list: %s", video_list.name)
    return jsonify(video_list.to_dict())


@bp.delete("/<int:list_id>")
def delete_list(path: ListPath):
    """Delete a video list and its associated videos."""
    video_list = VideoList.query.get(path.list_id)
    if not video_list:
        raise NotFoundError("VideoList", path.list_id)

    list_name = video_list.name
    video_count = video_list.videos.count()

    db.session.delete(video_list)
    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_DELETED,
        "list",
        path.list_id,
        {"name": list_name, "videos_deleted": video_count},
    )

    logger.info("Deleted list: %s (with %d videos)", list_name, video_count)
    return "", 204


def _build_list_tasks_query(list_id: int, limit: int | None):
    """Build query for tasks related to a list."""
    video_ids = [v.id for v in Video.query.filter_by(list_id=list_id).all()]
    q = Task.query.filter(
        db.or_(
            db.and_(Task.task_type == TaskType.SYNC.value, Task.entity_id == list_id),
            db.and_(
                Task.task_type == TaskType.DOWNLOAD.value, Task.entity_id.in_(video_ids)
            )
            if video_ids
            else db.false(),
        )
    ).order_by(Task.created_at.desc())
    return q.limit(limit) if limit else q


def _get_list_tasks_data(list_id: int, limit: int | None) -> list[dict]:
    """Get task data for a list."""
    tasks = _build_list_tasks_query(list_id, limit).all()
    entity_names = Task.batch_get_entity_names(tasks)
    return [t.to_dict(entity_name=entity_names.get(t.id)) for t in tasks]


def _get_list_tasks_fingerprint(list_id: int, limit: int | None) -> str:
    """Get fingerprint for task change detection."""
    tasks = (
        _build_list_tasks_query(list_id, limit)
        .with_entities(Task.id, Task.status)
        .all()
    )
    return ",".join(f"{t.id}:{t.status}" for t in tasks)


def _get_list_history_data(list_id: int, limit: int | None) -> list[dict]:
    """Get history data for a list."""
    q = History.query.filter(
        History.entity_type == "list", History.entity_id == list_id
    ).order_by(History.created_at.desc())
    if limit:
        q = q.limit(limit)
    return [e.to_dict() for e in q.all()]


def _get_list_history_fingerprint(list_id: int) -> tuple:
    """Get fingerprint for history change detection."""
    from sqlalchemy import func

    result = (
        db.session.query(func.count(History.id), func.max(History.created_at))
        .filter(History.entity_type == "list", History.entity_id == list_id)
        .first()
    )
    return (result[0], str(result[1]) if result[1] else None)


def _sse_stream(get_data, get_fingerprint):
    """Create an SSE stream generator."""
    app = current_app._get_current_object()

    def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with app.app_context():
                fingerprint = get_fingerprint()
                if fingerprint != last_fingerprint:
                    yield f"data: {json.dumps(get_data(), default=str)}\n\n"
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.get("/<int:list_id>/tasks")
def get_list_tasks(path: ListPath, query: ListTasksQuery):
    """Get tasks for a list. Supports SSE streaming."""
    if not VideoList.query.get(path.list_id):
        raise NotFoundError("VideoList", path.list_id)

    if request.accept_mimetypes.best != "text/event-stream":
        return jsonify(_get_list_tasks_data(path.list_id, query.limit))

    return _sse_stream(
        lambda: _get_list_tasks_data(path.list_id, query.limit),
        lambda: _get_list_tasks_fingerprint(path.list_id, query.limit),
    )


@bp.get("/<int:list_id>/history")
def get_list_history(path: ListPath, query: ListTasksQuery):
    """Get history for a list. Supports SSE streaming."""
    if not VideoList.query.get(path.list_id):
        raise NotFoundError("VideoList", path.list_id)

    if request.accept_mimetypes.best != "text/event-stream":
        return jsonify(_get_list_history_data(path.list_id, query.limit))

    return _sse_stream(
        lambda: _get_list_history_data(path.list_id, query.limit),
        lambda: _get_list_history_fingerprint(path.list_id),
    )
