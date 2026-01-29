"""Settings routes."""

import os

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.extensions import DB_DIALECT, engine, get_db
from app.models.settings import (
    DEFAULT_DATA_RETENTION_DAYS,
    SETTING_DATA_RETENTION_DAYS,
    Settings,
)
from app.schemas.settings import (
    DataRetentionResponse,
    DataRetentionUpdate,
    VacuumResponse,
    YtdlpUpdateResponse,
    YtdlpVersionResponse,
)

logger = get_logger("routes.settings")
router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/data-retention", response_model=DataRetentionResponse)
def get_data_retention(db: Session = Depends(get_db)):
    """Get data retention settings."""
    retention_days = Settings.get_int(
        db, SETTING_DATA_RETENTION_DAYS, DEFAULT_DATA_RETENTION_DAYS
    )
    return {"retention_days": retention_days}


@router.put("/data-retention", response_model=DataRetentionResponse)
def update_data_retention(payload: DataRetentionUpdate, db: Session = Depends(get_db)):
    """Update data retention settings."""
    Settings.set_int(db, SETTING_DATA_RETENTION_DAYS, payload.retention_days)
    logger.info("Updated data retention to %d days", payload.retention_days)
    return {"retention_days": payload.retention_days}


@router.post("/vacuum", response_model=VacuumResponse)
def vacuum_database():
    """
    Run VACUUM on SQLite database to reclaim disk space.

    This operation compacts the database file by rebuilding it, which can
    significantly reduce file size after deleting large amounts of data.

    Only available for SQLite databases. Returns an error for PostgreSQL.
    """
    if DB_DIALECT != "sqlite":
        return VacuumResponse(
            success=False,
            message="VACUUM is only available for SQLite databases. "
            "PostgreSQL handles this automatically.",
        )

    # Get database file path from engine URL
    db_path = str(engine.url).replace("sqlite:///", "")

    try:
        # Get size before vacuum
        size_before = os.path.getsize(db_path) if os.path.exists(db_path) else None

        # Run VACUUM - must be outside a transaction
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))

        # Get size after vacuum
        size_after = os.path.getsize(db_path) if os.path.exists(db_path) else None

        space_reclaimed = None
        if size_before is not None and size_after is not None:
            space_reclaimed = size_before - size_after

        logger.info(
            "Database vacuum completed. Before: %s, After: %s, Reclaimed: %s",
            size_before,
            size_after,
            space_reclaimed,
        )

        return VacuumResponse(
            success=True,
            message="Database vacuum completed successfully",
            size_before=size_before,
            size_after=size_after,
            space_reclaimed=space_reclaimed,
        )

    except Exception as e:
        logger.error("Database vacuum failed: %s", e)
        return VacuumResponse(
            success=False,
            message=f"Vacuum failed: {e!s}",
        )


@router.get("/ytdlp/version", response_model=YtdlpVersionResponse)
def get_ytdlp_version():
    """
    Get current yt-dlp version and check for updates.

    Returns the currently installed version and whether a newer
    nightly build is available.
    """
    import yt_dlp
    from yt_dlp.update import Updater

    current_version = yt_dlp.version.__version__
    channel = "nightly"

    try:
        ydl = yt_dlp.YoutubeDL({"quiet": True})
        updater = Updater(ydl, channel)
        update_info = updater.query_update()

        latest_version = update_info.version if update_info else current_version
        update_available = latest_version != current_version

        return YtdlpVersionResponse(
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            channel=channel,
        )
    except Exception as e:
        logger.warning("Failed to check yt-dlp updates: %s", e)
        return YtdlpVersionResponse(
            current_version=current_version,
            latest_version=None,
            update_available=False,
            channel=channel,
        )


@router.post("/ytdlp/update", response_model=YtdlpUpdateResponse)
def update_ytdlp():
    """
    Triggers an immediate update of yt-dlp to the latest available nightly channel build.
    """
    from app.tasks import update_ytdlp as do_update

    result = do_update()

    if result.get("success"):
        return YtdlpUpdateResponse(
            success=True,
            old_version=result["old_version"],
            new_version=result.get("new_version"),
            message=f"Updated from {result['old_version']} to {result.get('new_version', 'unknown')}",
        )
    else:
        return YtdlpUpdateResponse(
            success=False,
            old_version=result["old_version"],
            new_version=None,
            message=result.get("error", "Update failed"),
        )
