from datetime import datetime
from enum import Enum

from app.extensions import db


class SyncFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class VideoList(db.Model):
    """A channel or playlist to monitor for videos."""

    __tablename__ = "video_lists"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(200), nullable=False)
    url: str = db.Column(db.String(500), nullable=False, unique=True)
    list_type: str = db.Column(db.String(20), default="channel")
    extractor: str | None = db.Column(
        db.String(50), nullable=True
    )  # Platform identifier (e.g., "Youtube", "Vimeo")
    profile_id: int = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False
    )
    from_date: str | None = db.Column(db.String(8), nullable=True)  # YYYYMMDD format
    sync_frequency: str = db.Column(db.String(10), default=SyncFrequency.DAILY.value)
    enabled: bool = db.Column(db.Boolean, default=True)
    auto_download: bool = db.Column(
        db.Boolean,
        default=True,
    )
    last_synced: datetime | None = db.Column(db.DateTime, nullable=True)

    # Channel/playlist metadata (populated on sync)
    description: str | None = db.Column(db.Text, nullable=True)
    thumbnail: str | None = db.Column(db.String(500), nullable=True)
    tags: str | None = db.Column(db.Text, nullable=True)  # Comma-separated

    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profile = db.relationship("Profile", back_populates="lists")
    videos = db.relationship(
        "Video",
        back_populates="video_list",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def is_due_for_sync(self) -> bool:
        """Check if this list is due for a sync based on frequency."""
        if not self.last_synced:
            return True

        from datetime import timedelta

        now = datetime.utcnow()
        elapsed = now - self.last_synced

        if self.sync_frequency == SyncFrequency.DAILY.value:
            return elapsed >= timedelta(days=1)
        if self.sync_frequency == SyncFrequency.WEEKLY.value:
            return elapsed >= timedelta(weeks=1)
        if self.sync_frequency == SyncFrequency.MONTHLY.value:
            return elapsed >= timedelta(days=30)

        return True

    def to_dict(self, include_videos: bool = False) -> dict:
        data = {
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
            "description": self.description,
            "thumbnail": self.thumbnail,
            "tags": self.tags.split(",") if self.tags else [],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_videos:
            data["videos"] = [v.to_dict() for v in self.videos]
        return data
