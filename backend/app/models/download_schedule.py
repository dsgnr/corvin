"""Download schedule model."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Time

from app.models import Base


class DownloadSchedule(Base):
    """
    Download schedule configuration.

    Defines time windows when downloads are allowed to run.
    """

    __tablename__ = "download_schedules"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    # Days of week (comma-separated: "mon,tue,wed,thu,fri,sat,sun")
    days_of_week = Column(
        String(50), nullable=False, default="mon,tue,wed,thu,fri,sat,sun"
    )

    # Time window
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "days_of_week": self.days_of_week.split(",") if self.days_of_week else [],
            "start_time": self.start_time.strftime("%H:%M")
            if self.start_time
            else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def is_download_allowed(cls, db) -> bool:
        """
        Check if downloads are currently allowed based on schedules.

        If no schedules exist, downloads are always allowed.
        If schedules exist but none are enabled, downloads are always allowed.
        If enabled schedules exist, downloads are only allowed during scheduled windows.
        """
        from datetime import datetime

        schedules = db.query(cls).filter_by(enabled=True).all()

        # No enabled schedules = always allow
        if not schedules:
            return True

        now = datetime.now()
        current_day = now.strftime("%a").lower()
        current_time = now.time()

        for schedule in schedules:
            days = schedule.days_of_week.split(",") if schedule.days_of_week else []
            if current_day not in days:
                continue

            # Handle overnight schedules (e.g., 22:00 - 06:00)
            if schedule.start_time <= schedule.end_time:
                # Normal schedule (e.g., 09:00 - 17:00)
                if schedule.start_time <= current_time <= schedule.end_time:
                    return True
            else:
                # Overnight schedule (e.g., 22:00 - 06:00)
                if (
                    current_time >= schedule.start_time
                    or current_time <= schedule.end_time
                ):
                    return True

        return False
