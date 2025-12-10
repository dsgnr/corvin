from flask import Blueprint, request, jsonify

from app.extensions import db
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import Profile, HistoryAction
from app.models.profile import SponsorBlockBehavior, SPONSORBLOCK_CATEGORIES
from app.services import HistoryService

logger = get_logger("routes.profiles")
bp = Blueprint("profiles", __name__, url_prefix="/api/profiles")


def _validate_sponsorblock_categories(categories_str: str) -> None:
    """Validate SponsorBlock categories."""
    if not categories_str:
        return
    categories = [c.strip() for c in categories_str.split(",") if c.strip()]
    invalid = [c for c in categories if c not in SPONSORBLOCK_CATEGORIES]
    if invalid:
        raise ValidationError(
            f"Invalid SponsorBlock categories: {invalid}. "
            f"Valid categories: {SPONSORBLOCK_CATEGORIES}"
        )


def _validate_sponsorblock_behavior(behavior: str) -> None:
    """Validate SponsorBlock behavior."""
    if behavior and behavior not in SponsorBlockBehavior.ALL:
        raise ValidationError(
            f"Invalid SponsorBlock behavior: {behavior}. "
            f"Valid options: {SponsorBlockBehavior.ALL}"
        )


@bp.get("/sponsorblock-options")
def get_sponsorblock_options():
    """Get available SponsorBlock behaviors and categories."""
    return jsonify({
        "behaviors": SponsorBlockBehavior.ALL,
        "categories": SPONSORBLOCK_CATEGORIES,
        "category_labels": {
            "sponsor": "Sponsor",
            "intro": "Intro/Intermission",
            "outro": "Outro/Credits",
            "selfpromo": "Unpaid/Self Promotion",
            "preview": "Preview/Recap",
            "interaction": "Interaction Reminder (Subscribe)",
            "music_offtopic": "Music: Non-Music Section",
            "filler": "Tangents/Jokes",
        }
    })


@bp.post("/")
def create_profile():
    """Create a new profile."""
    data = request.get_json() or {}

    name = data.get("name")
    if not name:
        raise ValidationError("Name is required")

    if Profile.query.filter_by(name=name).first():
        raise ConflictError(f"Profile '{name}' already exists")

    # Validate SponsorBlock options
    _validate_sponsorblock_behavior(data.get("sponsorblock_behavior", ""))
    _validate_sponsorblock_categories(data.get("sponsorblock_categories", ""))

    profile = Profile(
        name=name,
        embed_metadata=data.get("embed_metadata", True),
        embed_thumbnail=data.get("embed_thumbnail", False),
        exclude_shorts=data.get("exclude_shorts", False),
        extra_args=data.get("extra_args", "{}"),
        # Subtitle options
        download_subtitles=data.get("download_subtitles", False),
        embed_subtitles=data.get("embed_subtitles", False),
        auto_generated_subtitles=data.get("auto_generated_subtitles", False),
        subtitle_languages=data.get("subtitle_languages", "en"),
        # Audio track language
        audio_track_language=data.get("audio_track_language", ""),
        # Output template
        output_template=data.get("output_template", "%(uploader)s/%(title)s.%(ext)s"),
        # SponsorBlock options
        sponsorblock_behavior=data.get("sponsorblock_behavior", SponsorBlockBehavior.DISABLED),
        sponsorblock_categories=data.get("sponsorblock_categories", ""),
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

    # Validate SponsorBlock options if provided
    if "sponsorblock_behavior" in data:
        _validate_sponsorblock_behavior(data["sponsorblock_behavior"])
    if "sponsorblock_categories" in data:
        _validate_sponsorblock_categories(data["sponsorblock_categories"])

    updatable_fields = [
        "embed_metadata",
        "embed_thumbnail",
        "exclude_shorts",
        "extra_args",
        # Subtitle options
        "download_subtitles",
        "embed_subtitles",
        "auto_generated_subtitles",
        "subtitle_languages",
        # Audio track language
        "audio_track_language",
        # Output template
        "output_template",
        # SponsorBlock options
        "sponsorblock_behavior",
        "sponsorblock_categories",
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
