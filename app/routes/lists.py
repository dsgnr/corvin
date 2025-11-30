from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import VideoList, Profile, HistoryAction
from app.services import HistoryService

logger = get_logger("routes.lists")
bp = Blueprint("lists", __name__, url_prefix="/api/lists")


@bp.post("/")
def create_list():
    """Create a new video list."""
    data = request.get_json() or {}

    _validate_create_data(data)

    from_date = _parse_from_date(data.get("from_date"))

    video_list = VideoList(
        name=data["name"],
        url=data["url"],
        list_type=data.get("list_type", "channel"),
        profile_id=data["profile_id"],
        from_date=from_date,
        enabled=data.get("enabled", True),
    )

    db.session.add(video_list)
    db.session.commit()

    HistoryService.log(
        HistoryAction.LIST_CREATED,
        "list",
        video_list.id,
        {"name": video_list.name, "url": video_list.url},
    )

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


def _parse_from_date(date_str: str | None):
    """Parse from_date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except ValueError:
        raise ValidationError("Invalid from_date format (use ISO format)")


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

    simple_fields = ["name", "list_type", "enabled"]
    for field in simple_fields:
        if field in data:
            setattr(video_list, field, data[field])
