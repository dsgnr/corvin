from datetime import datetime

from flask import Flask

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger("tasks")


def sync_single_list(app: Flask, list_id: int) -> dict:
    """Sync videos for a single list."""
    with app.app_context():
        return _execute_sync(list_id)


def _execute_sync(list_id: int) -> dict:
    """Execute the sync operation for a list (videos only, metadata already populated)."""
    import threading

    from app.extensions import db
    from app.models import HistoryAction, Video, VideoList
    from app.services import HistoryService, YtDlpService

    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    logger.info("Syncing list: %s", video_list.name)

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
        v.video_id for v in Video.query.filter_by(list_id=list_id).all()
    }

    include_shorts = video_list.profile.include_shorts
    counters = {"new": 0, "total": 0}
    lock = threading.Lock()

    def on_video_fetched(video_data: dict) -> None:
        # We're adding to the db here, so make sure we don't have
        # multiple threads writing to the db at any one time!
        with lock:
            counters["total"] += 1

            if not include_shorts and "shorts" in video_data.get("url", ""):
                return

            try:
                db.session.add(
                    Video(
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
                        list_id=video_list.id,
                    )
                )
                db.session.commit()
                counters["new"] += 1

                HistoryService.log(
                    HistoryAction.VIDEO_DISCOVERED,
                    "video",
                    details={"title": video_data["title"], "list_id": video_list.id},
                )
            except Exception:
                db.session.rollback()

    YtDlpService.extract_videos(url, from_date, on_video_fetched, existing_video_ids)

    video_list.last_synced = datetime.utcnow()
    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_SYNCED,
        "list",
        video_list.id,
        {"new_videos": counters["new"], "total_found": counters["total"]},
    )

    logger.info("List '%s' synced: %d new videos", video_list.name, counters["new"])
    return {"new_videos": counters["new"], "total_found": counters["total"]}


def _append_videos_path(url: str) -> str:
    """Append /videos to a YouTube channel URL to exclude shorts.

    Only applies to YouTube URLs - other platforms are returned unchanged.
    """
    # Only modify YouTube URLs
    if "youtube.com" not in url and "youtu.be" not in url:
        return url

    url = url.rstrip("/")
    if "/videos" not in url and "/shorts" not in url and "/streams" not in url:
        return f"{url}/videos"
    return url


def _video_exists(video_id: str, list_id: int) -> bool:
    """Check if a video already exists in the database."""
    from app.models import Video

    return Video.query.filter_by(video_id=video_id, list_id=list_id).first() is not None


def download_single_video(app: Flask, video_id: int) -> dict:
    """Download a single video."""
    with app.app_context():
        return _execute_download(video_id)


def _execute_download(video_id: int) -> dict:
    """Execute the download operation for a video."""
    from app.models import HistoryAction, Video
    from app.services import HistoryService, YtDlpService

    video = Video.query.get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)

    if video.downloaded:
        logger.info("Video already downloaded: %s", video.title)
        return {"status": "already_downloaded"}

    profile = video.video_list.profile
    logger.info("Downloading video: %s", video.title)

    HistoryService.log(
        HistoryAction.VIDEO_DOWNLOAD_STARTED,
        "video",
        video.id,
        {"title": video.title},
    )

    success, result, labels = YtDlpService.download_video(video, profile)

    if success:
        return _mark_download_success(video, result, labels)
    else:
        return _mark_download_failure(video, result)


def _mark_download_success(video, path: str, labels: dict) -> dict:
    """Mark video as successfully downloaded and update labels."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.extensions import db
    from app.models import HistoryAction
    from app.services import HistoryService

    video.downloaded = True
    video.download_path = path
    video.error_message = None

    if labels:
        existing_labels = video.labels or {}
        existing_labels.update(labels)
        video.labels = existing_labels
        flag_modified(video, "labels")

    db.session.commit()

    HistoryService.log(
        HistoryAction.VIDEO_DOWNLOAD_COMPLETED,
        "video",
        video.id,
        {"title": video.title, "path": path},
    )

    logger.info("Video '%s' downloaded to: %s", video.title, path)
    return {"status": "completed", "path": path}


def _mark_download_failure(video, error: str) -> dict:
    """Mark video download as failed."""
    from app.extensions import db
    from app.models import HistoryAction
    from app.services import HistoryService

    video.error_message = error
    db.session.commit()

    HistoryService.log(
        HistoryAction.VIDEO_DOWNLOAD_FAILED,
        "video",
        video.id,
        {"title": video.title, "error": error},
    )

    logger.error("Video %d download failed: %s", video.id, error)
    raise Exception(error)


def enqueue_task(task_type: str, entity_id: int, max_retries: int = 3):
    """Create a new task in the database if not already queued or running."""
    from app.extensions import db
    from app.models.task import Task, TaskStatus
    from app.task_queue import get_worker

    existing = (
        Task.query.filter_by(task_type=task_type, entity_id=entity_id)
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
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
    db.session.add(task)
    db.session.commit()

    logger.info("Enqueued task %d: %s/%d", task.id, task_type, entity_id)

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
    Returns dict with 'queued' count, 'skipped' count, and 'tasks' list.
    """
    from app.extensions import db
    from app.models.task import Task, TaskStatus
    from app.task_queue import get_worker

    # Find existing pending/running tasks for these entities
    existing = (
        Task.query.filter_by(task_type=task_type)
        .filter(Task.entity_id.in_(entity_ids))
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
        .all()
    )
    existing_ids = {t.entity_id for t in existing}

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
        db.session.add(task)
        tasks.append(task)

    if tasks:
        db.session.commit()

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


def schedule_syncs(list_ids: list[int] | None = None) -> dict:
    """
    Queue sync tasks for specified lists or all enabled lists that are due.
    Returns dict with queued/skipped counts.
    """
    from app.models import VideoList
    from app.models.task import TaskType

    if list_ids:
        # Validate list IDs exist and are enabled
        lists = VideoList.query.filter(
            VideoList.id.in_(list_ids), VideoList.enabled.is_(True)
        ).all()
        ids_to_queue = [vl.id for vl in lists]
    else:
        # All enabled lists that are due for sync based on their frequency
        lists = VideoList.query.filter_by(enabled=True).all()
        ids_to_queue = [vl.id for vl in lists if vl.is_due_for_sync()]

    if not ids_to_queue:
        return {"queued": 0, "skipped": 0, "tasks": []}

    result = enqueue_tasks_bulk(TaskType.SYNC.value, ids_to_queue)
    logger.info("Scheduled %d list syncs", result["queued"])
    return result


def schedule_all_syncs() -> dict:
    """Queue sync tasks for all enabled lists that are due (called by scheduler)."""
    return schedule_syncs()


def schedule_downloads(video_ids: list[int] | None = None) -> dict:
    """
    Queue download tasks for specified videos or all pending videos.
    Returns dict with queued/skipped counts.

    Note: Videos from lists with auto_download=False are excluded from automatic
    scheduling. They must be manually selected for download.
    """
    from app.models import Video, VideoList
    from app.models.task import TaskType

    if video_ids:
        # Validate video IDs exist and are not downloaded
        videos = Video.query.filter(
            Video.id.in_(video_ids), Video.downloaded.is_(False)
        ).all()
        ids_to_queue = [v.id for v in videos]
    else:
        # All pending videos from lists with auto_download enabled
        videos = (
            Video.query.join(VideoList)
            .filter(VideoList.auto_download.is_(True))
            .filter(Video.downloaded.is_(False))
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
