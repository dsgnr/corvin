"""
Task handlers and scheduling functions.

Contains the actual sync and download logic, plus functions for enqueueing
tasks and scheduling bulk operations.
"""

from datetime import datetime
from urllib.parse import urlparse

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.extensions import SessionLocal

logger = get_logger("tasks")


def _ensure_list_artwork(video_list) -> None:
    """
    Download list artwork if any files are missing.

    Delegates to YtDlpService.ensure_list_artwork.

    Args:
        video_list: The VideoList instance to check artwork for.
    """
    from app.services import YtDlpService

    YtDlpService.ensure_list_artwork(video_list.source_name, video_list.url)


def sync_single_list(list_id: int) -> dict:
    """
    Sync videos for a single list.

    Args:
        list_id: The VideoList ID to sync.

    Returns:
        Dictionary with new_videos and total_found counts.
    """
    return _execute_sync(list_id)


def _execute_sync(list_id: int) -> dict:
    """
    Execute the sync operation for a list.

    Fetches video metadata from the source URL and creates Video records
    for any new videos found. We check the database for existing video_id's
    so we don't fetch metadata for existing videos.

    Args:
        list_id: The VideoList ID to sync.

    Returns:
        Dictionary with new_videos and total_found counts.
    """
    import re
    import threading

    from app.models import HistoryAction, Video, VideoList
    from app.services import HistoryService, YtDlpService

    with SessionLocal() as db:
        video_list = db.query(VideoList).get(list_id)
        if not video_list:
            raise NotFoundError("VideoList", list_id)

        logger.info("Syncing list: %s", video_list.name)

        HistoryService.log(
            db,
            HistoryAction.LIST_SYNC_STARTED,
            "list",
            video_list.id,
            {"name": video_list.name},
        )

        from_date = (
            datetime.strptime(video_list.from_date, "%Y%m%d")
            if video_list.from_date
            else None
        )

        url = video_list.url
        if not video_list.profile.include_shorts:
            url = _append_videos_path(url)

        # Get existing video IDs to skip during extraction
        existing_video_ids = {
            v[0] for v in db.query(Video.video_id).filter_by(list_id=list_id).all()
        }

        include_shorts = video_list.profile.include_shorts
        include_live = video_list.profile.include_live
        counters = {"new": 0, "total": 0, "blacklisted": 0, "last_notified": 0}
        lock = threading.Lock()
        list_name = video_list.name

        # Compile blacklist regex if set
        blacklist_pattern = None
        if video_list.blacklist_regex and video_list.blacklist_regex.strip():
            try:
                blacklist_pattern = re.compile(
                    video_list.blacklist_regex, re.IGNORECASE
                )
            except re.error as e:
                logger.warning("Invalid blacklist regex for list %s: %s", list_name, e)

        # Import here to avoid circular imports
        from app.sse_hub import Channel, broadcast

    def on_video_fetched(video_data: dict) -> None:
        with lock:
            counters["total"] += 1

            if not include_shorts and "shorts" in video_data.get("url", ""):
                return

            if not include_live and video_data.get("was_live"):
                return

            try:
                with SessionLocal() as db_inner:
                    # Check if video title matches blacklist pattern
                    is_blacklisted = False
                    if blacklist_pattern and blacklist_pattern.search(
                        video_data["title"]
                    ):
                        is_blacklisted = True
                        counters["blacklisted"] += 1

                    video = Video(
                        video_id=video_data["video_id"],
                        title=video_data["title"],
                        description=video_data["description"],
                        url=video_data.get("url", ""),
                        duration=video_data.get("duration"),
                        upload_date=video_data.get("upload_date"),
                        thumbnail=video_data.get("thumbnail"),
                        extractor=video_data.get("extractor"),
                        media_type=video_data.get("media_type"),
                        labels=video_data.get("labels", {}),
                        list_id=list_id,
                        blacklisted=is_blacklisted,
                    )
                    db_inner.add(video)
                    db_inner.commit()
                    counters["new"] += 1

                    HistoryService.log(
                        db_inner,
                        HistoryAction.VIDEO_DISCOVERED,
                        "video",
                        video.id,
                        {
                            "name": list_name,
                            "title": video_data["title"],
                            "list_id": list_id,
                            "blacklisted": is_blacklisted,
                        },
                    )
                    broadcast(Channel.list_videos(list_id))
            except Exception:
                pass  # Rollback handled by context manager

    YtDlpService.extract_videos(url, from_date, on_video_fetched, existing_video_ids)

    with SessionLocal() as db:
        video_list = db.query(VideoList).get(list_id)
        video_list.last_synced = datetime.utcnow()
        db.commit()

        HistoryService.log(
            db,
            HistoryAction.LIST_SYNCED,
            "list",
            video_list.id,
            {
                "name": video_list.name,
                "new_videos": counters["new"],
                "total_found": counters["total"],
            },
        )

        # Broadcast to SSE subscribers
        broadcast(
            Channel.list_videos(list_id), Channel.list_history(list_id), Channel.LISTS
        )

        # Download artwork if missing
        _ensure_list_artwork(video_list)

    logger.info("List '%s' synced: %d new videos", list_name, counters["new"])
    return {"new_videos": counters["new"], "total_found": counters["total"]}


def _append_videos_path(url: str) -> str:
    """
    Append /videos to a YouTube channel URL to exclude shorts.

    Only applies to YouTube URLs - other platforms are returned unchanged.

    Args:
        url: The channel URL.

    Returns:
        Modified URL with /videos appended if applicable.
    """
    allowed_domains = {"youtube.com", "youtu.be", "twitch.tv"}

    hostname = urlparse(url).netloc.lower()

    if not any(domain in hostname for domain in allowed_domains):
        return url

    url = url.rstrip("/")
    if "/videos" not in url and "/shorts" not in url and "/streams" not in url:
        return f"{url}/videos"
    return url


def download_single_video(video_id: int) -> dict:
    """
    Download a single video.

    Args:
        video_id: The Video ID to download.

    Returns:
        Dictionary with status and path (if successful).
    """
    return _execute_download(video_id)


def _execute_download(video_id: int) -> dict:
    """
    Execute the download operation for a video.

    Uses the profile settings from the video's list to configure yt-dlp.

    Args:
        video_id: The Video ID to download.

    Returns:
        Dictionary with status and path (if successful).

    Raises:
        NotFoundError: If the video doesn't exist.
        Exception: If the download fails.
    """
    from app.models import HistoryAction, Video
    from app.services import HistoryService, YtDlpService

    with SessionLocal() as db:
        video = db.query(Video).get(video_id)
        if not video:
            raise NotFoundError("Video", video_id)

        if video.downloaded:
            logger.info("Video already downloaded: %s", video.title)
            return {"status": "already_downloaded"}

        profile = video.video_list.profile
        logger.info("Downloading video: %s", video.title)

        HistoryService.log(
            db,
            HistoryAction.VIDEO_DOWNLOAD_STARTED,
            "video",
            video.id,
            {
                "name": video.video_list.name,
                "title": video.title,
                "list_id": video.list_id,
            },
        )

        success, result, labels = YtDlpService.download_video(video, profile)

        if success:
            return _mark_download_success(db, video, result, labels)
        else:
            return _mark_download_failure(db, video, result)


def _mark_download_success(db, video, path: str, labels: dict) -> dict:
    """
    Mark a video as successfully downloaded and update labels.

    Args:
        db: Database session.
        video: The Video model instance.
        path: Path to the downloaded file.
        labels: Metadata labels extracted from the download.

    Returns:
        Dictionary with status and path.
    """
    from sqlalchemy.orm.attributes import flag_modified

    from app.models import HistoryAction
    from app.services import HistoryService
    from app.services.notifications import NotificationService
    from app.sse_hub import Channel, broadcast

    video.downloaded = True
    video.download_path = path
    video.error_message = None

    if labels:
        existing_labels = video.labels or {}
        existing_labels.update(labels)
        video.labels = existing_labels
        flag_modified(video, "labels")

    list_id = video.list_id
    list_name = video.video_list.name
    video_title = video.title
    db.commit()

    HistoryService.log(
        db,
        HistoryAction.VIDEO_DOWNLOAD_COMPLETED,
        "video",
        video.id,
        {"title": video_title, "path": path, "list_id": list_id},
    )

    # Send notifications (Plex library refresh, etc.)
    NotificationService.download_completed(video_title, path, list_name=list_name)

    logger.info("Video '%s' downloaded to: %s", video_title, path)
    channel = Channel.list_videos(list_id)
    logger.debug("Broadcasting to channel: %s", channel)
    broadcast(channel)
    return {"status": "completed", "path": path}


def _mark_download_failure(db, video, error: str) -> dict:
    """
    Mark a video download as failed.

    Args:
        db: Database session.
        video: The Video model instance.
        error: Error message describing the failure.

    Raises:
        Exception: Re-raises with the error message for task retry handling.
    """
    from app.models import HistoryAction
    from app.services import HistoryService
    from app.sse_hub import Channel, broadcast

    video.error_message = error
    list_id = video.list_id
    db.commit()

    HistoryService.log(
        db,
        HistoryAction.VIDEO_DOWNLOAD_FAILED,
        "video",
        video.id,
        {"title": video.title, "error": error, "list_id": list_id},
    )

    logger.error("Video %d download failed: %s", video.id, error)
    broadcast(Channel.list_videos(list_id))
    raise Exception(error)


def enqueue_task(task_type: str, entity_id: int, max_retries: int = 3):
    """
    Create a new task if not already queued or running.

    Args:
        task_type: The task type (e.g., "sync", "download").
        entity_id: The entity ID (list_id for sync, video_id for download).
        max_retries: Maximum retry attempts on failure.

    Returns:
        The created Task, or None if already queued.
    """
    from app.models.task import Task, TaskStatus
    from app.sse_hub import Channel, broadcast
    from app.task_queue import get_worker

    with SessionLocal() as db:
        existing = (
            db.query(Task)
            .filter_by(task_type=task_type, entity_id=entity_id)
            .filter(
                Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])
            )
            .first()
        )

        if existing:
            logger.info("Task already queued: %s/%d", task_type, entity_id)
            return None

        task = Task(
            task_type=task_type,
            entity_id=entity_id,
            status=TaskStatus.PENDING.value,
            max_retries=max_retries,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info("Enqueued task %d: %s/%d", task.id, task_type, entity_id)

        # Broadcast to SSE subscribers
        channels = [Channel.TASKS, Channel.TASKS_STATS]
        if task_type == "sync":
            channels.append(Channel.list_tasks(entity_id))
        broadcast(*channels)

        # Notify worker that new tasks are available
        worker = get_worker()
        if worker:
            worker.notify()

        return task


def enqueue_tasks_bulk(
    task_type: str, entity_ids: list[int], max_retries: int = 3
) -> dict:
    """
    Bulk enqueue multiple tasks, skipping duplicates.

    Args:
        task_type: The task type (e.g., "sync", "download").
        entity_ids: List of entity IDs to create tasks for.
        max_retries: Maximum retry attempts on failure.

    Returns:
        Dictionary with 'queued' count, 'skipped' count, and 'tasks' list.
    """
    from app.models.task import Task, TaskStatus
    from app.sse_hub import Channel, broadcast
    from app.task_queue import get_worker

    if not entity_ids:
        return {"queued": 0, "skipped": 0, "tasks": []}

    with SessionLocal() as db:
        # Find existing pending/running tasks for these entities
        # Batch the query to avoid SQLite's variable limit (999)
        existing_ids: set[int] = set()
        batch_size = 500
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i : i + batch_size]
            existing = (
                db.query(Task.entity_id)
                .filter_by(task_type=task_type)
                .filter(Task.entity_id.in_(batch))
                .filter(
                    Task.status.in_(
                        [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]
                    )
                )
                .all()
            )
            existing_ids.update(eid for (eid,) in existing)

        # Filter out duplicates
        new_ids = [eid for eid in entity_ids if eid not in existing_ids]

        tasks = []
        for entity_id in new_ids:
            task = Task(
                task_type=task_type,
                entity_id=entity_id,
                status=TaskStatus.PENDING.value,
                max_retries=max_retries,
            )
            db.add(task)
            tasks.append(task)

        if tasks:
            db.commit()

            # Broadcast to SSE subscribers
            broadcast(Channel.TASKS, Channel.TASKS_STATS)

            # Notify worker that new tasks are available
            worker = get_worker()
            if worker:
                worker.notify()

        logger.info(
            "Bulk enqueued %d %s tasks (%d skipped as duplicates)",
            len(tasks),
            task_type,
            len(existing_ids),
        )

        return {
            "queued": len(tasks),
            "skipped": len(entity_ids) - len(new_ids),
            "tasks": tasks,
        }


def schedule_syncs(list_ids: list[int] | None = None, force: bool = False) -> dict:
    """
    Queue sync tasks for specified lists or all enabled lists that are due.

    Args:
        list_ids: Specific list IDs to sync, or None for all enabled lists.
        force: If True, sync regardless of schedule. If False, only sync if due.

    Returns:
        Dictionary with queued/skipped counts.
    """
    from app.models import VideoList
    from app.models.task import TaskType

    with SessionLocal() as db:
        if list_ids:
            # Validate list IDs exist and are enabled
            lists = (
                db.query(VideoList)
                .filter(VideoList.id.in_(list_ids), VideoList.enabled.is_(True))
                .all()
            )
        else:
            # All enabled lists that are due for sync based on their frequency
            lists = db.query(VideoList).filter_by(enabled=True).all()

        if force:
            ids_to_queue = [vl.id for vl in lists]
        else:
            ids_to_queue = [vl.id for vl in lists if vl.is_due_for_sync()]

    if not ids_to_queue:
        return {"queued": 0, "skipped": 0, "tasks": []}

    result = enqueue_tasks_bulk(TaskType.SYNC.value, ids_to_queue)
    logger.info("Scheduled %d list syncs", result["queued"])
    return result


def schedule_all_syncs() -> dict:
    """
    Queue sync tasks for all enabled lists that are due.

    Called by the scheduler at regular intervals.

    Returns:
        Dictionary with queued/skipped counts.
    """
    return schedule_syncs()


def schedule_downloads(video_ids: list[int] | None = None) -> dict:
    """
    Queue download tasks for specified videos or all pending videos.

    Note: Videos from lists with auto_download=False are excluded from automatic
    scheduling. They must be manually selected for download.
    Blacklisted videos are also excluded from automatic scheduling.
    Downloads are only scheduled if allowed by download schedules.

    Args:
        video_ids: Specific video IDs to download, or None for all pending.

    Returns:
        Dictionary with queued/skipped counts.
    """
    from app.models import Video, VideoList
    from app.models.download_schedule import DownloadSchedule
    from app.models.task import TaskType

    with SessionLocal() as db:
        # Check if downloads are allowed by schedule (only for automatic scheduling)
        if video_ids is None and not DownloadSchedule.is_download_allowed(db):
            logger.info("Downloads not allowed by schedule, skipping")
            return {"queued": 0, "skipped": 0, "tasks": [], "reason": "schedule"}

        if video_ids:
            # Validate video IDs exist and are not downloaded
            videos = (
                db.query(Video)
                .filter(Video.id.in_(video_ids), Video.downloaded.is_(False))
                .all()
            )
            ids_to_queue = [v.id for v in videos]
        else:
            # All pending videos from lists with auto_download enabled
            # Exclude blacklisted videos from automatic downloads
            videos = (
                db.query(Video)
                .join(VideoList)
                .filter(VideoList.auto_download.is_(True))
                .filter(Video.downloaded.is_(False))
                .filter(Video.blacklisted.is_(False))
                .filter((Video.error_message.is_(None)) | (Video.retry_count > 0))
                .limit(100)
                .all()
            )
            ids_to_queue = [v.id for v in videos]

    if not ids_to_queue:
        return {"queued": 0, "skipped": 0, "tasks": []}

    result = enqueue_tasks_bulk(TaskType.DOWNLOAD.value, ids_to_queue)
    logger.info("Scheduled %d video downloads", result["queued"])
    return result
