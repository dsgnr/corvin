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
    """Execute the sync operation for a list."""
    from app.extensions import db
    from app.models import VideoList, HistoryAction
    from app.services import HistoryService, YtDlpService

    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    logger.info("Syncing list %d: %s", list_id, video_list.name)

    from_date = (
        datetime.combine(video_list.from_date, datetime.min.time())
        if video_list.from_date
        else None
    )

    videos_data = YtDlpService.extract_info(video_list.url, from_date)
    new_count = _store_discovered_videos(video_list, videos_data)

    video_list.last_synced = datetime.utcnow()
    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_SYNCED,
        "list",
        video_list.id,
        {"new_videos": new_count, "total_found": len(videos_data)},
    )

    logger.info("List %d synced: %d new videos", list_id, new_count)
    return {"new_videos": new_count, "total_found": len(videos_data)}


def _store_discovered_videos(video_list, videos_data: list[dict]) -> int:
    """Store newly discovered videos and return count."""
    from app.extensions import db
    from app.models import Video, HistoryAction
    from app.services import HistoryService

    new_count = 0
    exclude_shorts = video_list.profile.exclude_shorts

    for video_data in videos_data:
        if _video_exists(video_data["video_id"], video_list.id):
            continue

        # Skip shorts if profile has exclude_shorts enabled
        if exclude_shorts:
            if "shorts" in video_data.get("url"):
                continue

        video = Video(
            video_id=video_data["video_id"],
            title=video_data["title"],
            url=video_data["url"],
            duration=video_data.get("duration"),
            upload_date=video_data.get("upload_date"),
            thumbnail=video_data.get("thumbnail"),
            list_id=video_list.id,
        )
        db.session.add(video)
        new_count += 1

        HistoryService.log(
            HistoryAction.VIDEO_DISCOVERED,
            "video",
            details={"title": video_data["title"], "list_id": video_list.id},
        )

    return new_count


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
    from app.extensions import db
    from app.models import Video, HistoryAction
    from app.services import HistoryService, YtDlpService

    video = Video.query.get(video_id)
    if not video:
        raise NotFoundError("Video", video_id)

    if video.downloaded:
        logger.debug("Video %d already downloaded", video_id)
        return {"status": "already_downloaded"}

    profile = video.video_list.profile
    logger.info("Downloading video %d: %s", video_id, video.title)

    HistoryService.log(
        HistoryAction.VIDEO_DOWNLOAD_STARTED,
        "video",
        video.id,
        {"title": video.title},
    )

    success, result = YtDlpService.download_video(video, profile)

    if success:
        return _mark_download_success(video, result)
    else:
        return _mark_download_failure(video, result)


def _mark_download_success(video, path: str) -> dict:
    """Mark video as successfully downloaded."""
    from app.extensions import db
    from app.models import HistoryAction
    from app.services import HistoryService

    video.downloaded = True
    video.download_path = path
    video.error_message = None
    db.session.commit()

    HistoryService.log(
        HistoryAction.VIDEO_DOWNLOAD_COMPLETED,
        "video",
        video.id,
        {"title": video.title, "path": path},
    )

    logger.info("Video %d downloaded to: %s", video.id, path)
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
    """Create a new task in the database if not already queued."""
    from app.extensions import db
    from app.models.task import Task, TaskStatus

    existing = (
        Task.query.filter_by(task_type=task_type, entity_id=entity_id)
        .filter(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
        .first()
    )

    if existing:
        logger.debug("Task already queued: %s/%d", task_type, entity_id)
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
    return task


def schedule_all_syncs() -> int:
    """Queue sync tasks for all enabled lists."""
    from app.models import VideoList
    from app.models.task import TaskType

    lists = VideoList.query.filter_by(enabled=True).all()
    queued = 0

    for video_list in lists:
        if enqueue_task(TaskType.SYNC.value, video_list.id):
            queued += 1

    logger.info("Scheduled %d list syncs", queued)
    return queued


def schedule_pending_downloads() -> int:
    """Queue download tasks for pending videos."""
    from app.models import Video
    from app.models.task import TaskType

    videos = (
        Video.query.filter_by(downloaded=False)
        .filter((Video.error_message.is_(None)) | (Video.retry_count > 0))
        .limit(50)
        .all()
    )

    queued = 0
    for video in videos:
        if enqueue_task(TaskType.DOWNLOAD.value, video.id):
            queued += 1

    logger.info("Scheduled %d video downloads", queued)
    return queued
