from datetime import datetime

from flask import Blueprint, jsonify, request

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Profile, VideoList
from app.models.task import TaskType
from app.services import HistoryService
from app.services.ytdlp_service import YtDlpService
from app.tasks import enqueue_task

logger = get_logger("routes.lists")
bp = Blueprint("lists", __name__, url_prefix="/api/lists")


@bp.post("/")
def create_list():
    """Create a new video list."""
    data = request.get_json() or {}

    _validate_create_data(data)

    from_date = _parse_from_date(data.get("from_date"))

    metadata = {}
    try:
        metadata = YtDlpService.extract_list_metadata(data["url"])
    except Exception as e:
        logger.warning("Failed to fetch metadata for %s: %s", data["url"], e)

    video_list = VideoList(
        name=data["name"],
        url=data["url"],
        list_type=data.get("list_type", "channel"),
        profile_id=data["profile_id"],
        from_date=from_date,
        sync_frequency=data.get("sync_frequency", "daily"),
        enabled=data.get("enabled", True),
        auto_download=data.get("auto_download", True),
        # Populate from fetched metadata
        description=metadata.get("description"),
        thumbnail=metadata.get("thumbnail"),
        tags=",".join(metadata.get("tags", [])[:20]) if metadata.get("tags") else None,
        extractor=metadata.get("extractor"),
    )

    db.session.add(video_list)
    db.session.commit()

    # Download list artwork (fanart, poster, banner) if thumbnails available
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
            # Write channel/playlist NFO file
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

    # Auto-trigger sync for new list (videos only)
    if video_list.enabled:
        enqueue_task(TaskType.SYNC.value, video_list.id)
        logger.info("Auto-triggered sync for new list: %s", video_list.name)

    logger.info("Created list: %s", video_list.name)
    return jsonify(video_list.to_dict()), 201


def _validate_create_data(data: dict) -> None:
    """Validate list creation data."""
    required = ["name", "url", "profile_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    if not Profile.query.get(data["profile_id"]):
        raise NotFoundError("Profile", data["profile_id"])

    if VideoList.query.filter_by(url=data["url"]).first():
        raise ConflictError("List with this URL already exists")


def _parse_from_date(date_str: str | None) -> str | None:
    """Validate and return from_date in YYYYMMDD format."""
    if not date_str:
        return None
    # Remove any dashes if ISO format was provided
    clean = date_str.replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValidationError("Invalid from_date format (use YYYYMMDD)")
    # Validate it's a real date
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
def get_list(list_id: int):
    """Get a video list by ID."""
    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    include_videos = request.args.get("include_videos", "false").lower() == "true"
    return jsonify(video_list.to_dict(include_videos=include_videos))


@bp.put("/<int:list_id>")
def update_list(list_id: int):
    """Update a video list."""
    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    data = request.get_json() or {}
    if not data:
        raise ValidationError("No data provided")

    _apply_list_updates(video_list, data)

    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_UPDATED,
        "list",
        video_list.id,
        {"updated_fields": list(data.keys())},
    )

    logger.info("Updated list: %s", video_list.name)
    return jsonify(video_list.to_dict())


def _apply_list_updates(video_list: VideoList, data: dict) -> None:
    """Apply updates to a video list."""
    if "profile_id" in data:
        if not Profile.query.get(data["profile_id"]):
            raise NotFoundError("Profile", data["profile_id"])
        video_list.profile_id = data["profile_id"]

    if "url" in data and data["url"] != video_list.url:
        if VideoList.query.filter_by(url=data["url"]).first():
            raise ConflictError("List with this URL already exists")
        video_list.url = data["url"]

    if "from_date" in data:
        video_list.from_date = _parse_from_date(data["from_date"])

    simple_fields = ["name", "list_type", "sync_frequency", "enabled", "auto_download"]
    for field in simple_fields:
        if field in data:
            setattr(video_list, field, data[field])


@bp.delete("/<int:list_id>")
def delete_list(list_id: int):
    """Delete a video list and its associated videos."""
    video_list = VideoList.query.get(list_id)
    if not video_list:
        raise NotFoundError("VideoList", list_id)

    list_name = video_list.name
    video_count = video_list.videos.count()

    db.session.delete(video_list)
    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_DELETED,
        "list",
        list_id,
        {"name": list_name, "videos_deleted": video_count},
    )

    logger.info("Deleted list: %s (with %d videos)", list_name, video_count)
    return "", 204
