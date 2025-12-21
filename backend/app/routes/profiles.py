from flask import Blueprint, jsonify, request

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Profile
from app.models.profile import (
    OUTPUT_FORMATS,
    SPONSORBLOCK_CATEGORIES,
    SponsorBlockBehavior,
)
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


@bp.get("/options")
def get_profile_options():
    """Get profile options including defaults and SponsorBlock config."""
    return jsonify(
        {
            "defaults": {
                "output_template": Profile.output_template.default.arg,
                "embed_metadata": Profile.embed_metadata.default.arg,
                "embed_thumbnail": Profile.embed_thumbnail.default.arg,
                "exclude_shorts": Profile.exclude_shorts.default.arg,
                "download_subtitles": Profile.download_subtitles.default.arg,
                "embed_subtitles": Profile.embed_subtitles.default.arg,
                "auto_generated_subtitles": Profile.auto_generated_subtitles.default.arg,
                "subtitle_languages": Profile.subtitle_languages.default.arg,
                "audio_track_language": Profile.audio_track_language.default.arg,
                "sponsorblock_behavior": Profile.sponsorblock_behavior.default.arg,
                "sponsorblock_categories": Profile.sponsorblock_categories.default.arg,
                "output_format": Profile.output_format.default.arg,
                "extra_args": Profile.extra_args.default.arg,
            },
            "sponsorblock": {
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
                },
            },
            "output_formats": OUTPUT_FORMATS,
        }
    )


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

    # Build profile with provided values, falling back to model defaults
    profile = Profile(name=name)

    optional_fields = [
        "embed_metadata",
        "embed_thumbnail",
        "exclude_shorts",
        "extra_args",
        "download_subtitles",
        "embed_subtitles",
        "auto_generated_subtitles",
        "subtitle_languages",
        "audio_track_language",
        "output_template",
        "output_format",
        "sponsorblock_behavior",
        "sponsorblock_categories",
    ]
    for field in optional_fields:
        if field in data:
            setattr(profile, field, data[field])

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
        # Output format
        "output_format",
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
