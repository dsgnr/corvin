import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import and_, false, func, or_
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import SessionLocal, get_db
from app.models import HistoryAction, Profile, VideoList
from app.models.history import History
from app.models.task import Task, TaskType
from app.models.video import Video
from app.schemas.lists import ListCreate, ListUpdate
from app.services import HistoryService
from app.services.ytdlp_service import YtDlpService
from app.tasks import enqueue_task

logger = get_logger("routes.lists")
router = APIRouter(prefix="/api/lists", tags=["Lists"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_list(body: ListCreate, db: Session = Depends(get_db)):
    """Create a new video list."""
    if not db.query(Profile).get(body.profile_id):
        raise NotFoundError("Profile", body.profile_id)

    if db.query(VideoList).filter_by(url=body.url).first():
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

    db.add(video_list)
    db.commit()
    db.refresh(video_list)

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
        db,
        HistoryAction.LIST_CREATED,
        "list",
        video_list.id,
        {"name": video_list.name, "url": video_list.url},
    )

    if video_list.enabled:
        enqueue_task(TaskType.SYNC.value, video_list.id)
        logger.info("Auto-triggered sync for new list: %s", video_list.name)

    logger.info("Created list: %s", video_list.name)
    return video_list.to_dict()


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


@router.get("/")
async def list_all(request: Request, db: Session = Depends(get_db)):
    """List all video lists. Supports SSE streaming."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        lists = db.query(VideoList).all()
        return [vl.to_dict() for vl in lists]

    # SSE stream
    return EventSourceResponse(
        _sse_stream(
            lambda: [vl.to_dict() for vl in SessionLocal().query(VideoList).all()],
            lambda: _get_lists_fingerprint(),
        )
    )


def _get_lists_fingerprint() -> tuple:
    """Get fingerprint for lists change detection."""
    with SessionLocal() as db:
        result = db.query(
            func.count(VideoList.id),
            func.max(VideoList.created_at),
            func.max(VideoList.updated_at),
        ).first()
        return (
            result[0],
            str(result[1]) if result[1] else None,
            str(result[2]) if result[2] else None,
        )


@router.get("/{list_id}")
def get_list(
    list_id: int,
    include_videos: bool = Query(False),
    include_stats: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Get a video list by ID."""
    video_list = db.query(VideoList).get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)
    data = video_list.to_dict(include_videos=include_videos)
    if include_stats:
        data["stats"] = video_list.get_video_stats(db)
    return data


@router.put("/{list_id}")
def update_list(list_id: int, body: ListUpdate, db: Session = Depends(get_db)):
    """Update a video list."""
    video_list = db.query(VideoList).get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ValidationError("No data provided")

    if "profile_id" in data:
        if not db.query(Profile).get(data["profile_id"]):
            raise NotFoundError("Profile", data["profile_id"])

    if "url" in data and data["url"] != video_list.url:
        if db.query(VideoList).filter_by(url=data["url"]).first():
            raise ConflictError("List with this URL already exists")

    if "from_date" in data:
        data["from_date"] = _parse_from_date(data["from_date"])

    for field, value in data.items():
        setattr(video_list, field, value)

    db.commit()
    db.refresh(video_list)

    HistoryService.log(
        db,
        HistoryAction.LIST_UPDATED,
        "list",
        video_list.id,
        {"updated_fields": list(data.keys())},
    )

    logger.info("Updated list: %s", video_list.name)
    return video_list.to_dict()


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: int, db: Session = Depends(get_db)):
    """Delete a video list and its associated videos."""
    video_list = db.query(VideoList).get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    list_name = video_list.name
    video_count = video_list.videos.count()

    db.delete(video_list)
    db.commit()

    HistoryService.log(
        db,
        HistoryAction.LIST_DELETED,
        "list",
        list_id,
        {"name": list_name, "videos_deleted": video_count},
    )

    logger.info("Deleted list: %s (with %d videos)", list_name, video_count)


def _build_list_tasks_query(db, list_id: int, limit: int | None):
    """Build query for tasks related to a list."""
    video_ids = [v.id for v in db.query(Video).filter_by(list_id=list_id).all()]
    q = (
        db.query(Task)
        .filter(
            or_(
                and_(Task.task_type == TaskType.SYNC.value, Task.entity_id == list_id),
                and_(
                    Task.task_type == TaskType.DOWNLOAD.value,
                    Task.entity_id.in_(video_ids),
                )
                if video_ids
                else false(),
            )
        )
        .order_by(Task.created_at.desc())
    )
    return q.limit(limit) if limit else q


def _get_list_tasks_data(list_id: int, limit: int | None) -> list[dict]:
    """Get task data for a list."""
    with SessionLocal() as db:
        tasks = _build_list_tasks_query(db, list_id, limit).all()
        entity_names = Task.batch_get_entity_names(db, tasks)
        return [t.to_dict(entity_name=entity_names.get(t.id)) for t in tasks]


def _get_list_tasks_fingerprint(list_id: int, limit: int | None) -> str:
    """Get fingerprint for task change detection."""
    with SessionLocal() as db:
        tasks = (
            _build_list_tasks_query(db, list_id, limit)
            .with_entities(Task.id, Task.status)
            .all()
        )
        return ",".join(f"{t.id}:{t.status}" for t in tasks)


def _get_list_history_data(list_id: int, limit: int | None) -> list[dict]:
    """Get history data for a list."""
    with SessionLocal() as db:
        q = (
            db.query(History)
            .filter(History.entity_type == "list", History.entity_id == list_id)
            .order_by(History.created_at.desc())
        )
        if limit:
            q = q.limit(limit)
        return [e.to_dict() for e in q.all()]


def _get_list_history_fingerprint(list_id: int) -> tuple:
    """Get fingerprint for history change detection."""
    with SessionLocal() as db:
        result = (
            db.query(func.count(History.id), func.max(History.created_at))
            .filter(History.entity_type == "list", History.entity_id == list_id)
            .first()
        )
        return (result[0], str(result[1]) if result[1] else None)


async def _sse_stream(get_data, get_fingerprint):
    """Create an SSE stream generator."""
    last_fingerprint = None
    heartbeat_counter = 0

    while True:
        fingerprint = get_fingerprint()
        if fingerprint != last_fingerprint:
            yield {"data": json.dumps(get_data(), default=str)}
            last_fingerprint = fingerprint
            heartbeat_counter = 0
        else:
            heartbeat_counter += 1
            if heartbeat_counter >= 30:
                yield {"comment": "heartbeat"}
                heartbeat_counter = 0
        await asyncio.sleep(1)


@router.get("/{list_id}/tasks")
async def get_list_tasks(
    list_id: int,
    request: Request,
    limit: int = Query(100),
    db: Session = Depends(get_db),
):
    """Get tasks for a list. Supports SSE streaming."""
    if not db.query(VideoList).get(list_id):
        raise NotFoundError("VideoList", list_id)

    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        # Use injected session for non-SSE requests
        tasks = _build_list_tasks_query(db, list_id, limit).all()
        entity_names = Task.batch_get_entity_names(db, tasks)
        return [t.to_dict(entity_name=entity_names.get(t.id)) for t in tasks]

    return EventSourceResponse(
        _sse_stream(
            lambda: _get_list_tasks_data(list_id, limit),
            lambda: _get_list_tasks_fingerprint(list_id, limit),
        )
    )


@router.get("/{list_id}/history")
async def get_list_history(
    list_id: int,
    request: Request,
    limit: int = Query(100),
    db: Session = Depends(get_db),
):
    """Get history for a list. Supports SSE streaming."""
    if not db.query(VideoList).get(list_id):
        raise NotFoundError("VideoList", list_id)

    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        # Use injected session for non-SSE requests
        q = (
            db.query(History)
            .filter(History.entity_type == "list", History.entity_id == list_id)
            .order_by(History.created_at.desc())
        )
        if limit:
            q = q.limit(limit)
        return [e.to_dict() for e in q.all()]

    return EventSourceResponse(
        _sse_stream(
            lambda: _get_list_history_data(list_id, limit),
            lambda: _get_list_history_fingerprint(list_id),
        )
    )
