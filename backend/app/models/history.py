from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.sqlite import JSON

from app.models import Base


class HistoryAction(str, Enum):
    PROFILE_CREATED = "profile_created"
    PROFILE_UPDATED = "profile_updated"
    PROFILE_DELETED = "profile_deleted"
    LIST_CREATED = "list_created"
    LIST_UPDATED = "list_updated"
    LIST_DELETED = "list_deleted"
    LIST_SYNC_STARTED = "list_sync_started"
    LIST_SYNCED = "list_synced"
    VIDEO_DISCOVERED = "video_discovered"
    VIDEO_DOWNLOAD_STARTED = "video_download_started"
    VIDEO_DOWNLOAD_COMPLETED = "video_download_completed"
    VIDEO_DOWNLOAD_FAILED = "video_download_failed"
    VIDEO_RETRY = "video_retry"


class History(Base):
    """Audit log of actions performed in the system."""

    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_history_entity_type", "entity_type"),
        Index("ix_history_action", "action"),
        Index("ix_history_created_at", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details or {},
            "created_at": self.created_at.isoformat(),
        }
