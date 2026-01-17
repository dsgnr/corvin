from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import get_db
from app.models import HistoryAction, Profile
from app.models.profile import (
    OUTPUT_FORMATS,
    SPONSORBLOCK_CATEGORIES,
    SponsorBlockBehaviour,
)
from app.schemas.profiles import ProfileCreate, ProfileUpdate
from app.services import HistoryService

logger = get_logger("routes.profiles")
router = APIRouter(prefix="/api/profiles", tags=["Profiles"])


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


def _validate_sponsorblock_behaviour(behaviour: str) -> None:
    """Validate SponsorBlock behaviour."""
    if behaviour and behaviour not in SponsorBlockBehaviour.ALL:
        raise ValidationError(
            f"Invalid SponsorBlock behaviour: {behaviour}. "
            f"Valid options: {SponsorBlockBehaviour.ALL}"
        )


@router.get("/options")
def get_profile_options():
    """Get profile options including defaults and SponsorBlock config."""
    return {
        "defaults": {
            "output_template": "%(uploader)s/s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s",
            "embed_metadata": True,
            "embed_thumbnail": True,
            "include_shorts": True,
            "download_subtitles": False,
            "embed_subtitles": False,
            "auto_generated_subtitles": False,
            "subtitle_languages": "en",
            "audio_track_language": "en",
            "sponsorblock_behaviour": SponsorBlockBehaviour.DISABLED,
            "sponsorblock_categories": "",
            "output_format": "mp4",
            "extra_args": "{}",
        },
        "sponsorblock": {
            "behaviours": SponsorBlockBehaviour.ALL,
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


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    """Create a new profile."""
    if db.query(Profile).filter_by(name=body.name).first():
        raise ConflictError(f"Profile '{body.name}' already exists")

    _validate_sponsorblock_behaviour(body.sponsorblock_behaviour)
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
        sponsorblock_behaviour=body.sponsorblock_behaviour,
        sponsorblock_categories=body.sponsorblock_categories,
        output_format=body.output_format,
        extra_args=body.extra_args,
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


@router.get("/")
def list_profiles(db: Session = Depends(get_db)):
    """List all profiles."""
    profiles = db.query(Profile).all()
    return [p.to_dict() for p in profiles]


@router.get("/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    """Get a profile by ID."""
    profile = db.query(Profile).get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)
    return profile.to_dict()


@router.put("/{profile_id}")
def update_profile(profile_id: int, body: ProfileUpdate, db: Session = Depends(get_db)):
    """Update a profile."""
    profile = db.query(Profile).get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ValidationError("No data provided")

    if "name" in data and data["name"] != profile.name:
        if db.query(Profile).filter_by(name=data["name"]).first():
            raise ConflictError(f"Profile '{data['name']}' already exists")

    if "sponsorblock_behaviour" in data:
        _validate_sponsorblock_behaviour(data["sponsorblock_behaviour"])
    if "sponsorblock_categories" in data:
        _validate_sponsorblock_categories(data["sponsorblock_categories"])

    for field, value in data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    HistoryService.log(
        db,
        HistoryAction.PROFILE_UPDATED,
        "profile",
        profile.id,
        {"updated_fields": list(data.keys())},
    )

    logger.info("Updated profile: %s", profile.name)
    return profile.to_dict()


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """Delete a profile."""
    profile = db.query(Profile).get(profile_id)
    if not profile:
        raise NotFoundError("Profile", profile_id)

    list_count = profile.lists.count()
    if list_count > 0:
        raise ConflictError(
            f"Cannot delete profile '{profile.name}' - it has {list_count} associated list(s)"
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
