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
