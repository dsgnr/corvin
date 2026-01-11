from flask import jsonify
from flask_openapi3 import APIBlueprint, Tag

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import db
from app.models import HistoryAction, Profile
from app.models.profile import (
    OUTPUT_FORMATS,
    SPONSORBLOCK_CATEGORIES,
    SponsorBlockBehavior,
)
from app.schemas.profiles import ProfileCreate, ProfilePath, ProfileUpdate
from app.services import HistoryService

logger = get_logger("routes.profiles")
tag = Tag(name="Profiles", description="Download profile management")
bp = APIBlueprint("profiles", __name__, url_prefix="/api/profiles", abp_tags=[tag])


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
                "include_shorts": Profile.include_shorts.default.arg,
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
def create_profile(body: ProfileCreate):
    """Create a new profile."""
    if Profile.query.filter_by(name=body.name).first():
        raise ConflictError(f"Profile '{body.name}' already exists")

    _validate_sponsorblock_behavior(body.sponsorblock_behavior)
    _validate_sponsorblock_categories(body.sponsorblock_categories)

    profile = Profile(
        name=body.name,
        output_template=body.output_template,
        embed_metadata=body.embed_metadata,
        embed_thumbnail=body.embed_thumbnail,
        include_shorts=body.include_shorts,
        download_subtitles=body.download_subtitles,
        embed_subtitles=body.embed_subtitles,
        auto_generated_subtitles=body.auto_generated_subtitles,
        subtitle_languages=body.subtitle_languages,
        audio_track_language=body.audio_track_language,
        sponsorblock_behavior=body.sponsorblock_behavior,
        sponsorblock_categories=body.sponsorblock_categories,
        output_format=body.output_format,
        extra_args=body.extra_args,
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
def get_profile(path: ProfilePath):
    """Get a profile by ID."""
    profile = Profile.query.get(path.profile_id)
    if not profile:
        raise NotFoundError("Profile", path.profile_id)
    return jsonify(profile.to_dict())


@bp.put("/<int:profile_id>")
def update_profile(path: ProfilePath, body: ProfileUpdate):
    """Update a profile."""
    profile = Profile.query.get(path.profile_id)
    if not profile:
        raise NotFoundError("Profile", path.profile_id)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ValidationError("No data provided")

    if "name" in data and data["name"] != profile.name:
        if Profile.query.filter_by(name=data["name"]).first():
            raise ConflictError(f"Profile '{data['name']}' already exists")

    if "sponsorblock_behavior" in data:
        _validate_sponsorblock_behavior(data["sponsorblock_behavior"])
    if "sponsorblock_categories" in data:
        _validate_sponsorblock_categories(data["sponsorblock_categories"])

    for field, value in data.items():
        setattr(profile, field, value)

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
def delete_profile(path: ProfilePath):
    """Delete a profile."""
    profile = Profile.query.get(path.profile_id)
    if not profile:
        raise NotFoundError("Profile", path.profile_id)

    if profile.lists.count() > 0:
        raise ConflictError(
            f"Cannot delete profile '{profile.name}' - it has {profile.lists.count()} associated list(s)"
        )

    profile_name = profile.name
    db.session.delete(profile)
    db.session.commit()

    HistoryService.log(
        HistoryAction.PROFILE_DELETED,
        "profile",
        path.profile_id,
        {"name": profile_name},
    )

    logger.info("Deleted profile: %s", profile_name)
    return "", 204
