from flask import Blueprint, request, jsonify

from app.extensions import db
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import Profile, HistoryAction
from app.services import HistoryService

logger = get_logger("routes.profiles")
bp = Blueprint("profiles", __name__, url_prefix="/api/profiles")


@bp.post("/")
def create_profile():
    """Create a new profile."""
    data = request.get_json() or {}

    name = data.get("name")
    if not name:
        raise ValidationError("Name is required")

    if Profile.query.filter_by(name=name).first():
        raise ConflictError(f"Profile '{name}' already exists")

    profile = Profile(
        name=name,
        sponsorblock_remove=data.get("sponsorblock_remove", ""),
        embed_metadata=data.get("embed_metadata", True),
        embed_thumbnail=data.get("embed_thumbnail", False),
        exclude_shorts=data.get("exclude_shorts", False),
        extra_args=data.get("extra_args", "{}"),
    )

    db.session.add(profile)
    db.session.commit()

    HistoryService.log(
        HistoryAction.PROFILE_CREATED, "profile", profile.id, {"name": profile.name}
    )

    logger.info("Created profile: %s", profile.name)
    return jsonify(profile.to_dict()), 201


@bp.get("/")
def list_profiles():
    """List all profiles."""
    profiles = Profile.query.all()
    return jsonify([p.to_dict() for p in profiles])


@bp.get("/<int:profile_id>")
def get_profile(profile_id: int):
    """Get a profile by ID."""
    profile = Profile.query.get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)
    return jsonify(profile.to_dict())


@bp.put("/<int:profile_id>")
def update_profile(profile_id: int):
    """Update a profile."""
    profile = Profile.query.get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    data = request.get_json() or {}
    if not data:
        raise ValidationError("No data provided")

    if "name" in data and data["name"] != profile.name:
        if Profile.query.filter_by(name=data["name"]).first():
            raise ConflictError(f"Profile '{data['name']}' already exists")
        profile.name = data["name"]

    updatable_fields = [
        "sponsorblock_remove",
        "embed_metadata",
        "embed_thumbnail",
        "exclude_shorts",
        "extra_args",
    ]
    for field in updatable_fields:
        if field in data:
            setattr(profile, field, data[field])

    db.session.commit()

    HistoryService.log(
        HistoryAction.PROFILE_UPDATED,
        "profile",
        profile.id,
        {"updated_fields": list(data.keys())},
    )

    logger.info("Updated profile: %s", profile.name)
    return jsonify(profile.to_dict())


@bp.delete("/<int:profile_id>")
def delete_profile(profile_id: int):
    """Delete a profile."""
    profile = Profile.query.get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    if profile.lists.count() > 0:
        raise ConflictError(
            f"Cannot delete profile '{profile.name}' - it has {profile.lists.count()} associated list(s)"
        )

    profile_name = profile.name
    db.session.delete(profile)
    db.session.commit()

    HistoryService.log(
        HistoryAction.PROFILE_DELETED, "profile", profile_id, {"name": profile_name}
    )

    logger.info("Deleted profile: %s", profile_name)
    return "", 204
