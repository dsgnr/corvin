from datetime import datetime
from enum import Enum

from app.extensions import db


class HistoryAction(str, Enum):
    PROFILE_CREATED = "profile_created"
    PROFILE_UPDATED = "profile_updated"
    LIST_CREATED = "list_created"
    LIST_UPDATED = "list_updated"
    LIST_SYNCED = "list_synced"
    VIDEO_DISCOVERED = "video_discovered"
    VIDEO_DOWNLOAD_STARTED = "video_download_started"
    VIDEO_DOWNLOAD_COMPLETED = "video_download_completed"
    VIDEO_DOWNLOAD_FAILED = "video_download_failed"
    VIDEO_RETRY = "video_retry"


class History(db.Model):
    """Audit log of actions performed in the system."""

    __tablename__ = "history"

    id: int = db.Column(db.Integer, primary_key=True)
    action: str = db.Column(db.String(50), nullable=False)
    entity_type: str = db.Column(db.String(50), nullable=False)
    entity_id: int | None = db.Column(db.Integer, nullable=True)
    details: str = db.Column(db.Text, default="{}")
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
