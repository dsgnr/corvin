"""Download schedules routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import get_db
from app.models.download_schedule import DownloadSchedule
from app.schemas.schedules import (
    ScheduleCreate,
    ScheduleResponse,
    ScheduleStatusResponse,
    ScheduleUpdate,
)

logger = get_logger("routes.schedules")
router = APIRouter(prefix="/api/schedules", tags=["Schedules"])


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(db: Session = Depends(get_db)):
    """Get all download schedules."""
    schedules = db.query(DownloadSchedule).order_by(DownloadSchedule.name).all()
    return [s.to_dict() for s in schedules]


@router.get("/status", response_model=ScheduleStatusResponse)
def get_schedule_status(db: Session = Depends(get_db)):
    """Check if downloads are currently allowed based on schedules."""
    active_count = db.query(DownloadSchedule).filter_by(enabled=True).count()
    return {
        "downloads_allowed": DownloadSchedule.is_download_allowed(db),
        "active_schedules": active_count,
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduleResponse)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    """Create a new download schedule."""
    schedule = DownloadSchedule(
        name=payload.name,
        enabled=payload.enabled,
        days_of_week=",".join(payload.days_of_week),
        start_time=datetime.strptime(payload.start_time, "%H:%M").time(),
        end_time=datetime.strptime(payload.end_time, "%H:%M").time(),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    logger.info("Created download schedule: %s", schedule.name)
    return schedule.to_dict()


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Get a schedule by ID."""
    schedule = db.get(DownloadSchedule, schedule_id)
    if not schedule:
        raise NotFoundError("DownloadSchedule", schedule_id)
    return schedule.to_dict()


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int, payload: ScheduleUpdate, db: Session = Depends(get_db)
):
    """Update a download schedule."""
    schedule = db.get(DownloadSchedule, schedule_id)
    if not schedule:
        raise NotFoundError("DownloadSchedule", schedule_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationError("No data provided")

    if "days_of_week" in update_data:
        update_data["days_of_week"] = ",".join(update_data["days_of_week"])

    if "start_time" in update_data:
        update_data["start_time"] = datetime.strptime(
            update_data["start_time"], "%H:%M"
        ).time()

    if "end_time" in update_data:
        update_data["end_time"] = datetime.strptime(
            update_data["end_time"], "%H:%M"
        ).time()

    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)

    logger.info("Updated download schedule: %s", schedule.name)
    return schedule.to_dict()


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Delete a download schedule."""
    schedule = db.get(DownloadSchedule, schedule_id)
    if not schedule:
        raise NotFoundError("DownloadSchedule", schedule_id)

    name = schedule.name
    db.delete(schedule)
    db.commit()

    logger.info("Deleted download schedule: %s", name)
