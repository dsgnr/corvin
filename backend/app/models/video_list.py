"""
VideoList model for channels and playlists.
"""

from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models import Base

# Sync frequency options in hours
SYNC_FREQUENCIES = {
    "hourly": 1,
    "6h": 6,
    "12h": 12,
    "daily": 24,
    "weekly": 168,
    "monthly": 720,
}


class VideoList(Base):
    """
    A channel or playlist to monitor for videos.
    """

    __tablename__ = "video_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    list_type = Column(String(20), default="channel")
    extractor = Column(String(50), nullable=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    from_date = Column(String(8), nullable=True)
    sync_frequency = Column(String(10), default="daily")
    enabled = Column(Boolean, default=True)
    auto_download = Column(Boolean, default=True)
    last_synced = Column(DateTime, nullable=True)
    deleting = Column(Boolean, default=False)

    description = Column(Text, nullable=True)
    thumbnail = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="lists")
    videos = relationship(
        "Video",
        back_populates="video_list",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def is_due_for_sync(self) -> bool:
        """
        Check if this list is due for a sync based on its frequency.

        Returns:
            True if sync is due, False otherwise.
        """
        if not self.last_synced:
            return True

        hours = SYNC_FREQUENCIES.get(self.sync_frequency, 24)
        return datetime.utcnow() - self.last_synced >= timedelta(hours=hours)

    def next_sync_at(self) -> datetime | None:
        """
        Calculate when the next sync is due.

        Returns:
            Datetime of next scheduled sync, or None if never synced.
        """
        if not self.last_synced:
            return None

        hours = SYNC_FREQUENCIES.get(self.sync_frequency, 24)
        return self.last_synced + timedelta(hours=hours)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialisation."""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "list_type": self.list_type,
            "extractor": self.extractor,
            "profile_id": self.profile_id,
            "from_date": self.from_date,
            "sync_frequency": self.sync_frequency,
            "enabled": self.enabled,
            "auto_download": self.auto_download,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "next_sync_at": self.next_sync_at().isoformat()
            if self.next_sync_at()
            else None,
            "description": self.description,
            "thumbnail": self.thumbnail,
            "tags": self.tags.split(",") if self.tags else [],
            "deleting": self.deleting,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def get_video_stats(self, db) -> dict:
        """
        Get video statistics.

        Args:
            db: Database session.

        Returns:
            Dictionary with total, downloaded, failed, and pending counts.
        """
        from sqlalchemy import case, func

        from app.models.video import Video

        stats = (
            db.query(
                func.count(Video.id).label("total"),
                func.sum(case((Video.downloaded.is_(True), 1), else_=0)).label(
                    "downloaded"
                ),
                func.sum(case((Video.error_message.isnot(None), 1), else_=0)).label(
                    "failed"
                ),
            )
            .filter(Video.list_id == self.id)
            .first()
        )

        return {
            "total": stats.total or 0,
            "downloaded": stats.downloaded or 0,
            "failed": stats.failed or 0,
            "pending": (stats.total or 0)
            - (stats.downloaded or 0)
            - (stats.failed or 0),
        }
