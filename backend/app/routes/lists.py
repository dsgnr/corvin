"""
Lists routes.
"""

import asyncio
import json
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, load_only
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.helpers import parse_from_date
from app.core.logging import get_logger
from app.extensions import ReadSessionLocal, SessionLocal, get_db, sse_executor
from app.models import HistoryAction, Profile, VideoList
from app.models.history import History
from app.models.task import Task, TaskStatus, TaskType
from app.models.video import Video
from app.schemas.common import DeletionStartedResponse
from app.schemas.lists import (
    BulkListCreate,
    HistoryPaginatedResponse,
    ListCreate,
    ListResponse,
    ListUpdate,
    ListVideoStatsResponse,
    TasksPaginatedResponse,
    VideosPaginatedResponse,
)
from app.schemas.videos import VideoResponse
from app.services import HistoryService
from app.services.ytdlp_service import YtDlpService
from app.sse_hub import Channel, broadcast, hub
from app.sse_stream import sse_cors_headers, sse_response, wants_sse
from app.tasks import enqueue_task

logger = get_logger("routes.lists")
router = APIRouter(prefix="/api/lists", tags=["Lists"])

ACTIVE_TASK_STATUSES = (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)


def _reapply_blacklist_background(
    list_id: int,
    list_name: str,
    blacklist_regex: str | None,
    min_duration: int | None,
    max_duration: int | None,
):
    """
    Re-evaluate all videos in a list against blacklist criteria in batches.

    Runs in a background thread to avoid blocking the API for large lists.

    Args:
        list_id: The VideoList ID to reapply blacklist for.
        list_name: Name of the list for logging.
        blacklist_regex: The regex pattern to match against video titles.
        min_duration: Minimum video duration in seconds.
        max_duration: Maximum video duration in seconds.
    """
    import re
    import time

    BATCH_SIZE = 2000

    pattern = None
    if blacklist_regex:
        try:
            pattern = re.compile(blacklist_regex, re.IGNORECASE)
        except re.error as e:
            logger.warning("Invalid blacklist regex for list %s: %s", list_name, e)

    total_changed = 0

    with SessionLocal() as db:
        try:
            # Process in batches using offset
            offset = 0
            while True:
                videos = (
                    db.query(Video)
                    .options(
                        load_only(
                            Video.id,
                            Video.title,
                            Video.duration,
                            Video.blacklisted,
                            Video.error_message,
                        )
                    )
                    .filter(Video.list_id == list_id)
                    .order_by(Video.id)
                    .offset(offset)
                    .limit(BATCH_SIZE)
                    .all()
                )

                if not videos:
                    break

                batch_changed = 0
                blacklisted_video_ids = []
                for video in videos:
                    # Collect all blacklist reasons
                    blacklist_reasons = []

                    # Check regex pattern
                    if pattern and pattern.search(video.title):
                        blacklist_reasons.append("Title matches blacklist pattern")

                    # Check duration constraints
                    if video.duration is not None:
                        if min_duration is not None and video.duration < min_duration:
                            blacklist_reasons.append(
                                f"Duration ({video.duration}s) is below minimum ({min_duration}s)"
                            )
                        if max_duration is not None and video.duration > max_duration:
                            blacklist_reasons.append(
                                f"Duration ({video.duration}s) exceeds maximum ({max_duration}s)"
                            )

                    should_be_blacklisted = len(blacklist_reasons) > 0
                    blacklist_reason = (
                        "; ".join(blacklist_reasons) if blacklist_reasons else None
                    )

                    # Update if changed
                    if (
                        video.blacklisted != should_be_blacklisted
                        or video.error_message != blacklist_reason
                    ):
                        video.blacklisted = should_be_blacklisted
                        video.error_message = blacklist_reason
                        batch_changed += 1
                        # Track newly blacklisted videos to cancel their tasks
                        if should_be_blacklisted:
                            blacklisted_video_ids.append(video.id)

                if batch_changed:
                    # Cancel any pending download tasks for newly blacklisted videos
                    if blacklisted_video_ids:
                        db.query(Task).filter(
                            Task.task_type == TaskType.DOWNLOAD.value,
                            Task.entity_id.in_(blacklisted_video_ids),
                            Task.status == TaskStatus.PENDING.value,
                        ).update(
                            {Task.status: TaskStatus.CANCELLED.value},
                            synchronize_session=False,
                        )

                    db.commit()
                    total_changed += batch_changed
                    # Notify after each batch so UI updates progressively
                    broadcast(Channel.list_videos(list_id), Channel.TASKS)

                offset += BATCH_SIZE
                time.sleep(0.05)  # yield time to other connections

            if total_changed:
                logger.info(
                    "Reapplied blacklist for list %s: %d videos changed",
                    list_name,
                    total_changed,
                )

        except Exception as e:
            logger.error("Failed to reapply blacklist for list %s: %s", list_name, e)
            db.rollback()
        finally:
            # Final notification to ensure UI is up to date
            broadcast(Channel.list_videos(list_id))


def _list_exists(db: Session, list_id: int) -> bool:
    return db.query(exists().where(VideoList.id == list_id)).scalar()


def _get_list_stats(db: Session, list_id: int) -> dict:
    """Get video statistics for a list."""
    stats = (
        db.query(
            func.count(Video.id).label("total"),
            func.count().filter(Video.downloaded.is_(True)).label("downloaded"),
            func.count().filter(Video.error_message.isnot(None)).label("failed"),
        )
        .filter(Video.list_id == list_id)
        .first()
    )

    total = stats.total or 0
    downloaded = stats.downloaded or 0
    failed = stats.failed or 0
    pending = max(0, total - downloaded - failed)

    return {
        "total": total,
        "downloaded": downloaded,
        "failed": failed,
        "pending": pending,
    }


def _fetch_video_stats(db: Session, list_id: int) -> dict:
    """Fetch list stats."""
    stats = (
        db.query(
            func.count(Video.id).label("total"),
            func.count().filter(Video.downloaded.is_(True)).label("downloaded"),
            func.count()
            .filter(Video.downloaded.is_(False), Video.error_message.isnot(None))
            .label("failed"),
            func.count().filter(Video.blacklisted.is_(True)).label("blacklisted"),
            func.max(Video.id).label("newest_id"),
            func.max(Video.updated_at).label("last_updated"),
        )
        .filter(Video.list_id == list_id)
        .one()
    )

    total = stats.total or 0
    downloaded = stats.downloaded or 0
    failed = stats.failed or 0
    blacklisted = stats.blacklisted or 0
    pending = max(0, total - downloaded - failed)

    return {
        "total": total,
        "downloaded": downloaded,
        "failed": failed,
        "pending": pending,
        "blacklisted": blacklisted,
        "newest_id": stats.newest_id,
        "last_updated": stats.last_updated.isoformat() if stats.last_updated else None,
    }


def _fetch_active_tasks(db: Session, list_id: int) -> dict:
    """Fetch active tasks for a list."""
    result = {
        "sync": {"pending": [], "running": []},
        "download": {"pending": [], "running": []},
    }

    # Sync tasks
    sync_rows = (
        db.query(Task.status, Task.entity_id)
        .filter(
            Task.task_type == TaskType.SYNC.value,
            Task.entity_id == list_id,
            Task.status.in_(ACTIVE_TASK_STATUSES),
        )
        .all()
    )
    for task_status, entity_id in sync_rows:
        if task_status in result["sync"]:
            result["sync"][task_status].append(entity_id)

    # Download tasks
    download_rows = (
        db.query(Task.status, Task.entity_id)
        .join(Video, Task.entity_id == Video.id)
        .filter(
            Task.task_type == TaskType.DOWNLOAD.value,
            Video.list_id == list_id,
            Task.status.in_(ACTIVE_TASK_STATUSES),
        )
        .all()
    )
    for task_status, entity_id in download_rows:
        if task_status in result["download"]:
            result["download"][task_status].append(entity_id)

    return result


def _fetch_changed_video_ids(
    db: Session, list_id: int, since: datetime, limit: int = 100
) -> list[int]:
    """Fetch video IDs updated since a given timestamp."""
    rows = (
        db.query(Video.id)
        .filter(Video.list_id == list_id, Video.updated_at > since)
        .order_by(Video.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def _fetch_all_lists() -> list[dict]:
    with ReadSessionLocal() as db:
        return [vl.to_dict() for vl in db.query(VideoList).all()]


def _fetch_list_tasks(
    list_id: int, page: int, page_size: int, search: str | None
) -> dict:
    """Fetch paginated tasks for a list."""
    with ReadSessionLocal() as db:
        task_cols = [
            Task.id,
            Task.task_type,
            Task.entity_id,
            Task.status,
            Task.result,
            Task.error,
            Task.retry_count,
            Task.max_retries,
            Task.created_at,
            Task.started_at,
            Task.completed_at,
        ]

        # Base queries
        sync_query = (
            db.query(*task_cols, VideoList.name.label("entity_name"))
            .join(VideoList, Task.entity_id == VideoList.id)
            .filter(Task.task_type == TaskType.SYNC.value, Task.entity_id == list_id)
        )

        download_query = (
            db.query(*task_cols, Video.title.label("entity_name"))
            .join(Video, Task.entity_id == Video.id)
            .filter(Task.task_type == TaskType.DOWNLOAD.value, Video.list_id == list_id)
        )

        # Apply search filter
        if search:
            pattern = f"%{search}%"
            sync_query = sync_query.filter(
                VideoList.name.ilike(pattern)
                | Task.status.ilike(pattern)
                | Task.task_type.ilike(pattern)
            )
            download_query = download_query.filter(
                Video.title.ilike(pattern)
                | Task.status.ilike(pattern)
                | Task.task_type.ilike(pattern)
            )

        # Combine queries with UNION ALL
        combined_query = sync_query.union_all(download_query)

        # Get total count in one go
        total = combined_query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)

        # Apply pagination
        rows = (
            combined_query.order_by(Task.created_at.desc())
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


def _fetch_list_history(
    list_id: int, page: int, page_size: int, search: str | None
) -> dict:
    """Fetch paginated history for a list."""
    from sqlalchemy import or_

    from app.extensions import json_text

    with ReadSessionLocal() as db:
        # Include both list events and video events for this list
        # Video events store list_id in the details JSON
        details_text = json_text(History.details)
        query = db.query(History).filter(
            or_(
                # List-level events
                (History.entity_type == "list") & (History.entity_id == list_id),
                # Video events that belong to this list (stored in details.list_id)
                (History.entity_type == "video")
                & (details_text.like(f'%"list_id": {list_id}%')),
            )
        )

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                History.action.ilike(pattern) | details_text.ilike(pattern)
            )

        # Get total count
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)

        # Fetch paginated entries
        entries = (
            query.order_by(History.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "entries": [h.to_dict() for h in entries],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


def _create_video_list(
    db: Session,
    url: str,
    name: str | None,
    list_type: str,
    profile_id: int,
    sync_frequency: str | None = None,
    enabled: bool = True,
    auto_download: bool = False,
    from_date: str | None = None,
    blacklist_regex: str | None = None,
    min_duration: int | None = None,
    max_duration: int | None = None,
    bulk: bool = False,
) -> VideoList:
    """
    Create a VideoList with metadata extraction, artwork download, and history logging.

    Args:
        db: Database session
        url: The list URL
        name: Optional name (if None, derived from metadata or URL)
        list_type: Type of list (channel, playlist, etc.)
        profile_id: Associated profile ID
        sync_frequency: How often to sync
        enabled: Whether the list is enabled
        auto_download: Whether to auto-download new videos
        from_date: Optional date filter string
        blacklist_regex: Optional regex for blacklisting videos
        min_duration: Minimum video duration in seconds
        max_duration: Maximum video duration in seconds
        bulk: Whether this is part of a bulk creation (for history logging)

    Returns:
        The created VideoList instance
    """
    try:
        list_metadata = YtDlpService.extract_list_metadata(url)
    except Exception as exc:
        logger.error("Failed to fetch metadata for %s: %s", url, exc)
        raise ValidationError(f"Failed to fetch list metadata: {exc}") from exc

    # Use provided name, fall back to metadata name, then URL as last resort
    resolved_name = name or list_metadata.get("name") or url

    video_list = VideoList(
        name=resolved_name,
        source_name=list_metadata.get("name"),
        url=url,
        list_type=list_type,
        profile_id=profile_id,
        from_date=parse_from_date(from_date) if from_date else None,
        sync_frequency=sync_frequency,
        enabled=enabled,
        auto_download=auto_download,
        blacklist_regex=blacklist_regex,
        min_duration=min_duration,
        max_duration=max_duration,
        description=list_metadata.get("description"),
        thumbnail=list_metadata.get("thumbnail"),
        tags=",".join(list_metadata.get("tags", [])[:20])
        if list_metadata.get("tags")
        else None,
        extractor=list_metadata.get("extractor"),
    )

    db.add(video_list)
    db.commit()
    db.refresh(video_list)

    # Download artwork
    YtDlpService.ensure_list_artwork(
        video_list.source_name, video_list.url, list_metadata
    )

    history_details = {"name": video_list.name, "url": video_list.url}
    if bulk:
        history_details["bulk"] = True

    HistoryService.log(
        db,
        HistoryAction.LIST_CREATED,
        "list",
        video_list.id,
        history_details,
    )

    enqueue_task(TaskType.SYNC.value, video_list.id)
    logger.info("Auto-triggered sync for new list: %s", video_list.name)

    log_suffix = " (bulk)" if bulk else ""
    logger.info("Created list%s: %s", log_suffix, video_list.name)

    return video_list


def _create_video_list_background(
    url: str,
    name: str | None,
    list_type: str,
    profile_id: int,
    sync_frequency: str | None,
    enabled: bool,
    auto_download: bool,
    from_date: str | None,
    blacklist_regex: str | None,
    bulk: bool = False,
):
    """Create a video list in a background thread."""
    with SessionLocal() as db:
        try:
            _create_video_list(
                db=db,
                url=url,
                name=name,
                list_type=list_type,
                profile_id=profile_id,
                sync_frequency=sync_frequency,
                enabled=enabled,
                auto_download=auto_download,
                from_date=from_date,
                blacklist_regex=blacklist_regex,
                bulk=bulk,
            )
            broadcast(Channel.LISTS)
        except Exception as exc:
            logger.error("Failed to create list for %s: %s", url, exc)
            db.rollback()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ListResponse)
def create_list(
    payload: ListCreate,
    db: Session = Depends(get_db),
):
    """Create a new list."""
    if not db.get(Profile, payload.profile_id):
        raise NotFoundError("Profile", payload.profile_id)

    if db.query(VideoList).filter_by(url=payload.url).first():
        raise ConflictError("List with this URL already exists")

    video_list = _create_video_list(
        db=db,
        url=payload.url,
        name=payload.name,
        list_type=payload.list_type,
        profile_id=payload.profile_id,
        sync_frequency=payload.sync_frequency,
        enabled=payload.enabled,
        auto_download=payload.auto_download,
        from_date=payload.from_date,
        blacklist_regex=payload.blacklist_regex,
        min_duration=payload.min_duration,
        max_duration=payload.max_duration,
    )

    broadcast(Channel.LISTS)
    return video_list.to_dict()


def _create_lists_bulk_background(
    urls: list[str],
    profile_id: int,
    list_type: str,
    sync_frequency: str,
    enabled: bool,
    auto_download: bool,
):
    """Create multiple lists in a background thread."""
    with SessionLocal() as db:
        for url in urls:
            url = url.strip()
            if not url:
                continue

            if db.query(VideoList).filter_by(url=url).first():
                logger.warning("Skipping duplicate URL: %s", url)
                continue

            try:
                _create_video_list(
                    db=db,
                    url=url,
                    name=None,
                    list_type=list_type,
                    profile_id=profile_id,
                    sync_frequency=sync_frequency,
                    enabled=enabled,
                    auto_download=auto_download,
                    bulk=True,
                )
                broadcast(Channel.LISTS)
            except Exception as exc:
                db.rollback()
                logger.error("Failed to create list for %s: %s", url, exc)


@router.post("/bulk", status_code=status.HTTP_202_ACCEPTED)
def create_lists_bulk(
    payload: BulkListCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create multiple lists from a list of URLs."""
    if not db.get(Profile, payload.profile_id):
        raise NotFoundError("Profile", payload.profile_id)

    background_tasks.add_task(
        _create_lists_bulk_background,
        payload.urls,
        payload.profile_id,
        payload.list_type,
        payload.sync_frequency,
        payload.enabled,
        payload.auto_download,
    )

    return {"message": "Bulk list creation started", "count": len(payload.urls)}


@router.get("", response_model=list[ListResponse])
async def list_all(request: Request):
    """Get all lists. Supports SSE streaming."""
    if not wants_sse(request):
        with ReadSessionLocal() as db:
            return [vl.to_dict() for vl in db.query(VideoList).all()]

    return sse_response(request, Channel.LISTS, _fetch_all_lists)


@router.get("/{list_id}", response_model=ListResponse)
async def get_list(list_id: int):
    """Get a list by ID."""

    def _fetch():
        with ReadSessionLocal() as db:
            video_list = db.get(VideoList, list_id)
            return video_list.to_dict() if video_list else None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(sse_executor, _fetch)
    if result is None:
        raise NotFoundError("VideoList", list_id)
    return result


@router.put("/{list_id}", response_model=ListResponse)
def update_list(list_id: int, payload: ListUpdate, db: Session = Depends(get_db)):
    """Update a list."""
    video_list = db.get(VideoList, list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationError("No data provided")

    if "profile_id" in update_data and not db.get(Profile, update_data["profile_id"]):
        raise NotFoundError("Profile", update_data["profile_id"])

    if "url" in update_data and update_data["url"] != video_list.url:
        if db.query(VideoList).filter_by(url=update_data["url"]).first():
            raise ConflictError("List with this URL already exists")

    if "from_date" in update_data:
        update_data["from_date"] = parse_from_date(update_data["from_date"])

    # Check if blacklist_regex is changing
    blacklist_changed = (
        "blacklist_regex" in update_data
        and update_data["blacklist_regex"] != video_list.blacklist_regex
    )

    # Check if duration filters are changing
    duration_changed = (
        "min_duration" in update_data
        and update_data["min_duration"] != video_list.min_duration
    ) or (
        "max_duration" in update_data
        and update_data["max_duration"] != video_list.max_duration
    )

    for field, value in update_data.items():
        setattr(video_list, field, value)

    db.commit()
    db.refresh(video_list)

    # Re-evaluate existing videos if blacklist criteria changed
    if blacklist_changed or duration_changed:
        thread = threading.Thread(
            target=_reapply_blacklist_background,
            args=(
                video_list.id,
                video_list.name,
                video_list.blacklist_regex,
                video_list.min_duration,
                video_list.max_duration,
            ),
            daemon=True,
        )
        thread.start()

    HistoryService.log(
        db,
        HistoryAction.LIST_UPDATED,
        "list",
        video_list.id,
        {"updated_fields": list(update_data.keys())},
    )

    logger.info("Updated list: %s", video_list.name)
    broadcast(Channel.LISTS, Channel.list_history(video_list.id))
    return video_list.to_dict()


def _delete_list_background(list_id: int, list_name: str):
    """Delete a list and all associated videos/tasks in SQLite."""
    import time

    BATCH_SIZE = 2000  # safe for SQLite concurrency

    with SessionLocal() as db:
        try:
            # Count videos before deletion
            video_count = (
                db.query(func.count(Video.id)).filter(Video.list_id == list_id).scalar()
                or 0
            )

            # Cancel all pending/paused SYNC tasks in bulk
            cancelled_sync = (
                db.query(Task)
                .filter(
                    Task.task_type == TaskType.SYNC.value,
                    Task.entity_id == list_id,
                    Task.status.in_(
                        [TaskStatus.PENDING.value, TaskStatus.PAUSED.value]
                    ),
                )
                .update(
                    {Task.status: TaskStatus.CANCELLED.value}, synchronize_session=False
                )
            )

            # Cancel all pending/paused DOWNLOAD tasks in bulk
            # Use subquery since SQLAlchemy doesn't allow update() after join()
            video_ids_subquery = select(Video.id).where(Video.list_id == list_id)
            cancelled_download = (
                db.query(Task)
                .filter(
                    Task.task_type == TaskType.DOWNLOAD.value,
                    Task.entity_id.in_(video_ids_subquery),
                    Task.status.in_(
                        [TaskStatus.PENDING.value, TaskStatus.PAUSED.value]
                    ),
                )
                .update(
                    {Task.status: TaskStatus.CANCELLED.value}, synchronize_session=False
                )
            )

            db.commit()  # single commit for all task cancellations

            # Batch delete videos
            while True:
                video_ids = [
                    vid
                    for (vid,) in db.query(Video.id)
                    .filter(Video.list_id == list_id)
                    .limit(BATCH_SIZE)
                ]
                if not video_ids:
                    break

                db.query(Video).filter(Video.id.in_(video_ids)).delete(
                    synchronize_session=False
                )
                db.commit()  # commit each batch
                time.sleep(0.05)  # yield time to other connections

            # Delete the list itself
            video_list = db.get(VideoList, list_id)
            if video_list:
                db.delete(video_list)
                db.commit()

            # Log deletion in history
            HistoryService.log(
                db,
                HistoryAction.LIST_DELETED,
                "list",
                None,  # not linking to deleted list
                {"name": list_name, "videos_deleted": video_count},
            )

            logger.info(
                "Deleted list: %s (videos: %d, cancelled tasks: %d)",
                list_name,
                video_count,
                cancelled_sync + cancelled_download,
            )

        except Exception as e:
            logger.error("Failed to delete list %s: %s", list_name, e)
            db.rollback()
            # Reset deleting flag on error
            video_list = db.get(VideoList, list_id)
            if video_list:
                video_list.deleting = False
                db.commit()
        finally:
            broadcast(
                Channel.LISTS, Channel.TASKS, Channel.TASKS_STATS, Channel.HISTORY
            )


@router.delete(
    "/{list_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeletionStartedResponse,
)
def delete_list(list_id: int, db: Session = Depends(get_db)):
    """Mark a list for deletion.

    Since lists can have millions of videos,
    we drop the actual delete steps into a thread so we don't lock the db.
    """
    video_list = db.get(VideoList, list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    if video_list.deleting:
        raise ConflictError("List is already being deleted")

    # Check for running sync tasks
    running_sync = (
        db.query(Task)
        .filter(
            Task.task_type == TaskType.SYNC.value,
            Task.entity_id == list_id,
            Task.status == TaskStatus.RUNNING.value,
        )
        .count()
    )
    if running_sync > 0:
        raise ConflictError("Cannot delete list while sync is running")

    # Check for running download tasks using JOIN
    running_download = (
        db.query(Task)
        .join(Video, Task.entity_id == Video.id)
        .filter(
            Task.task_type == TaskType.DOWNLOAD.value,
            Video.list_id == list_id,
            Task.status == TaskStatus.RUNNING.value,
        )
        .count()
    )
    if running_download > 0:
        raise ConflictError(
            f"Cannot delete list while {running_download} download(s) are running"
        )

    # Mark as deleting
    list_name = video_list.name
    video_list.deleting = True
    db.commit()
    broadcast(Channel.LISTS)

    # Run deletion in background thread
    thread = threading.Thread(
        target=_delete_list_background,
        args=(list_id, list_name),
        daemon=True,
    )
    thread.start()

    return {"message": "List deletion started"}


@router.get("/{list_id}/tasks", response_model=TasksPaginatedResponse)
async def get_list_tasks(
    list_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
    """Get paginated tasks for a list. Supports SSE streaming."""
    if not wants_sse(request):
        return _fetch_list_tasks(list_id, page, page_size, search)

    return sse_response(
        request,
        Channel.list_tasks(list_id),
        lambda: _fetch_list_tasks(list_id, page, page_size, search),
    )


@router.get("/{list_id}/history", response_model=HistoryPaginatedResponse)
async def get_list_history(
    list_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
    """Get paginated history for a list. Supports SSE streaming."""
    if not wants_sse(request):
        return _fetch_list_history(list_id, page, page_size, search)

    return sse_response(
        request,
        Channel.list_history(list_id),
        lambda: _fetch_list_history(list_id, page, page_size, search),
    )


def _fetch_videos_paginated(
    list_id: int,
    page: int,
    page_size: int,
    downloaded: bool | None = None,
    failed: bool | None = None,
    blacklisted: bool | None = None,
    search: str | None = None,
) -> dict:
    """Fetch paginated videos for SSE streaming."""
    with ReadSessionLocal() as db:
        query = db.query(Video).filter(Video.list_id == list_id)

        # Apply filters
        if downloaded is not None:
            query = query.filter(Video.downloaded == downloaded)

        if failed is True:
            query = query.filter(Video.error_message.isnot(None))
        elif failed is False:
            query = query.filter(Video.error_message.is_(None))

        if blacklisted is not None:
            query = query.filter(Video.blacklisted == blacklisted)

        if search:
            pattern = f"%{search}%"
            query = query.filter(Video.title.ilike(pattern))

        # Total count for pagination
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)

        # Fetch paginated rows
        rows = (
            query.options(
                load_only(
                    Video.id,
                    Video.video_id,
                    Video.title,
                    Video.duration,
                    Video.upload_date,
                    Video.media_type,
                    Video.thumbnail,
                    Video.downloaded,
                    Video.blacklisted,
                    Video.error_message,
                    Video.labels,
                )
            )
            .order_by(Video.upload_date.desc().nulls_last(), Video.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # Convert to dict
        videos = [
            {
                "id": v.id,
                "video_id": v.video_id,
                "title": v.title,
                "duration": v.duration,
                "upload_date": v.upload_date.isoformat() if v.upload_date else None,
                "media_type": v.media_type,
                "thumbnail": v.thumbnail,
                "downloaded": v.downloaded,
                "blacklisted": v.blacklisted,
                "error_message": v.error_message,
                "labels": v.labels or {},
            }
            for v in rows
        ]

        return {
            "videos": videos,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


@router.get("/{list_id}/videos", response_model=VideosPaginatedResponse)
async def get_videos_page(
    list_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    downloaded: bool | None = Query(None),
    failed: bool | None = Query(None),
    blacklisted: bool | None = Query(None),
    search: str | None = Query(None),
):
    """
    Get paginated videos for a list.

    Supports:
    - Standard JSON response
    - SSE stream if Accept header includes 'text/event-stream'
    """
    # SSE streaming mode
    if wants_sse(request):
        return sse_response(
            request,
            Channel.list_videos(list_id),
            lambda: _fetch_videos_paginated(
                list_id, page, page_size, downloaded, failed, blacklisted, search
            ),
        )

    # Regular JSON response
    with ReadSessionLocal() as db:
        if not _list_exists(db, list_id):
            raise NotFoundError("VideoList", list_id)

        # Delegate filtering & pagination to the optimised function
        result = _fetch_videos_paginated(
            list_id, page, page_size, downloaded, failed, blacklisted, search
        )
        return result


@router.get("/{list_id}/videos/stats", response_model=ListVideoStatsResponse)
async def get_list_video_stats(list_id: int, request: Request):
    """
    Get list statistics and active tasks.

    Supports two modes:
    - Regular JSON response for standard requests
    - SSE stream if Accept header includes 'text/event-stream'
    """
    if not wants_sse(request):
        with ReadSessionLocal() as db:
            if not _list_exists(db, list_id):
                raise NotFoundError("VideoList", list_id)
            return {
                "stats": _fetch_video_stats(db, list_id),
                "tasks": _fetch_active_tasks(db, list_id),
            }

    # Check list exists before starting stream
    with ReadSessionLocal() as db:
        if not _list_exists(db, list_id):
            raise NotFoundError("VideoList", list_id)

    async def generate_sse_stream():
        event_loop = asyncio.get_running_loop()
        last_change_check = datetime.utcnow()
        heartbeat_interval = 30

        def fetch_payload(since_timestamp: datetime):
            with ReadSessionLocal() as db:
                return {
                    "stats": _fetch_video_stats(db, list_id),
                    "tasks": _fetch_active_tasks(db, list_id),
                    "changed_video_ids": _fetch_changed_video_ids(
                        db, list_id, since_timestamp
                    ),
                }

        # Send initial data
        payload = await event_loop.run_in_executor(
            sse_executor, fetch_payload, last_change_check
        )
        yield {"data": json.dumps(payload, default=str)}
        last_change_check = datetime.utcnow()

        async with hub.subscribe(Channel.list_videos(list_id)) as notification_queue:
            while True:
                try:
                    await asyncio.wait_for(
                        notification_queue.get(), timeout=heartbeat_interval
                    )
                    payload = await event_loop.run_in_executor(
                        sse_executor, fetch_payload, last_change_check
                    )
                    yield {"data": json.dumps(payload, default=str)}
                    last_change_check = datetime.utcnow()
                except TimeoutError:
                    yield {"comment": "heartbeat"}

    return EventSourceResponse(generate_sse_stream(), headers=sse_cors_headers(request))


@router.get("/{list_id}/videos/by-ids", response_model=list[VideoResponse])
def get_videos_by_ids(
    list_id: int, ids: str = Query(...), db: Session = Depends(get_db)
):
    """Get videos by their IDs within a list."""
    if not _list_exists(db, list_id):
        raise NotFoundError("VideoList", list_id)

    try:
        video_ids = [int(v) for v in ids.split(",") if v]
    except ValueError as exc:
        raise ValidationError("Invalid video ID format") from exc

    if not video_ids:
        return []
    if len(video_ids) > 100:
        raise ValidationError("Maximum 100 video IDs per request")

    return [
        v.to_dict()
        for v in db.query(Video).filter(
            Video.list_id == list_id, Video.id.in_(video_ids)
        )
    ]
