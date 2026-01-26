"""
Profiles routes.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.constants import (
    AUDIO_CODECS,
    DEFAULT_OUTPUT_TEMPLATE,
    RESOLUTION_MAP,
    SPONSORBLOCK_BEHAVIOURS,
    SPONSORBLOCK_CATEGORIES,
    SPONSORBLOCK_DISABLED,
    VIDEO_CODECS,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.validators import (
    validate_sponsorblock_behaviour,
    validate_sponsorblock_categories,
)
from app.extensions import get_db, get_read_db
from app.models import HistoryAction, Profile
from app.schemas.profiles import (
    ProfileCreate,
    ProfileOptionsResponse,
    ProfileResponse,
    ProfileUpdate,
)
from app.services import HistoryService

logger = get_logger("routes.profiles")
router = APIRouter(prefix="/api/profiles", tags=["Profiles"])


@router.get("/options", response_model=ProfileOptionsResponse)
def get_profile_options():
    """Return profile defaults and supported configuration options."""
    resolutions = []
    for height, label in RESOLUTION_MAP.items():
        if height == 0:
            resolutions.append({"label": label, "value": height})
        else:
            resolutions.append({"label": f"{label} ({height}p)", "value": height})

    video_codecs = sorted(
        [{"label": label, "value": value} for value, label in VIDEO_CODECS.items()],
        key=lambda x: x["label"],
    )

    audio_codecs = sorted(
        [{"label": label, "value": value} for value, label in AUDIO_CODECS.items()],
        key=lambda x: x["label"],
    )

    return {
        "defaults": {
            "output_template": DEFAULT_OUTPUT_TEMPLATE,
            "embed_metadata": True,
            "embed_thumbnail": True,
            "include_shorts": True,
            "include_live": True,
            "download_subtitles": False,
            "embed_subtitles": False,
            "auto_generated_subtitles": False,
            "subtitle_languages": "en",
            "audio_track_language": "en",
            "sponsorblock_behaviour": SPONSORBLOCK_DISABLED,
            "sponsorblock_categories": [],
            "output_format": None,
            "preferred_resolution": None,
            "preferred_video_codec": None,
            "preferred_audio_codec": None,
            "extra_args": "{}",
        },
        "sponsorblock": {
            "behaviours": SPONSORBLOCK_BEHAVIOURS,
            "categories": list(SPONSORBLOCK_CATEGORIES.keys()),
            "category_labels": SPONSORBLOCK_CATEGORIES,
        },
        "resolutions": resolutions,
        "video_codecs": video_codecs,
        "audio_codecs": audio_codecs,
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProfileResponse)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    """Create a profile."""
    existing_profile = db.query(Profile).filter_by(name=payload.name).first()
    if existing_profile:
        raise ConflictError(f"Profile '{payload.name}' already exists")

    validate_sponsorblock_behaviour(payload.sponsorblock_behaviour)
    validate_sponsorblock_categories(payload.sponsorblock_categories)

    profile = Profile(
        name=payload.name,
        output_template=payload.output_template,
        embed_metadata=payload.embed_metadata,
        embed_thumbnail=payload.embed_thumbnail,
        include_shorts=payload.include_shorts,
        include_live=payload.include_live,
        download_subtitles=payload.download_subtitles,
        embed_subtitles=payload.embed_subtitles,
        auto_generated_subtitles=payload.auto_generated_subtitles,
        subtitle_languages=payload.subtitle_languages,
        audio_track_language=payload.audio_track_language,
        sponsorblock_behaviour=payload.sponsorblock_behaviour,
        sponsorblock_categories=payload.sponsorblock_categories,
        output_format=payload.output_format,
        preferred_resolution=payload.preferred_resolution,
        preferred_video_codec=payload.preferred_video_codec,
        preferred_audio_codec=payload.preferred_audio_codec,
        extra_args=payload.extra_args,
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    HistoryService.log(
        db,
        HistoryAction.PROFILE_CREATED,
        "profile",
        profile.id,
        {"name": profile.name},
    )

    logger.info("Created profile: %s", profile.name)
    return profile.to_dict()


@router.get("", response_model=list[ProfileResponse])
def list_profiles(db: Session = Depends(get_read_db)):
    """Get all profiles."""
    profiles = db.query(Profile).all()
    return [profile.to_dict() for profile in profiles]


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: int, db: Session = Depends(get_read_db)):
    """Get a single profile by ID."""
    profile = db.get(Profile, profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    return profile.to_dict()


@router.put("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing profile."""
    profile = db.get(Profile, profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationError("No data provided")

    if "name" in update_data and update_data["name"] != profile.name:
        if db.query(Profile).filter_by(name=update_data["name"]).first():
            raise ConflictError(f"Profile '{update_data['name']}' already exists")

    if "sponsorblock_behaviour" in update_data:
        validate_sponsorblock_behaviour(update_data["sponsorblock_behaviour"])

    if "sponsorblock_categories" in update_data:
        validate_sponsorblock_categories(update_data["sponsorblock_categories"])

    for field_name, field_value in update_data.items():
        setattr(profile, field_name, field_value)

    db.commit()
    db.refresh(profile)

    HistoryService.log(
        db,
        HistoryAction.PROFILE_UPDATED,
        "profile",
        profile.id,
        {"updated_fields": list(update_data.keys())},
    )

    logger.info("Updated profile: %s", profile.name)
    return profile.to_dict()


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """Delete a profile.

    Checks whether the profile is in use first.
    """
    profile = db.get(Profile, profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    associated_list_count = profile.lists.count()
    if associated_list_count > 0:
        raise ConflictError(
            f"Cannot delete profile '{profile.name}' - "
            f"it has {associated_list_count} associated list(s)"
        )

    profile_name = profile.name
    db.delete(profile)
    db.commit()

    HistoryService.log(
        db,
        HistoryAction.PROFILE_DELETED,
        "profile",
        profile_id,
        {"name": profile_name},
    )

    logger.info("Deleted profile: %s", profile_name)
