from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.models import Base


class Video(Base):
    """An individual video discovered from a list."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    video_id = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    duration = Column(Integer, nullable=True)
    upload_date = Column(DateTime, nullable=True)
    thumbnail = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    extractor = Column(
        String(50), nullable=True
    )  # Platform identifier (e.g., "Youtube", "Vimeo")
    media_type = Column(
        String(20), nullable=False, default="video"
    )  # "video" or "short"
    labels = Column(
        JSON, nullable=True, default=dict
    )  # Video metadata labels (resolution, codec, etc.)
    list_id = Column(Integer, ForeignKey("video_lists.id"), nullable=False)
    downloaded = Column(Boolean, default=False)
    download_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    video_list = relationship("VideoList", back_populates="videos")

    __table_args__ = (
        UniqueConstraint("video_id", "list_id", name="uq_video_list"),
        Index("ix_videos_list_id", "list_id"),
        Index("ix_videos_downloaded", "downloaded"),
        Index("ix_videos_list_downloaded", "list_id", "downloaded"),
        Index("ix_videos_list_created", "list_id", "created_at"),  # For ORDER BY
        Index("ix_videos_list_updated", "list_id", "updated_at"),  # For incremental SSE
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "duration": self.duration,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "thumbnail": self.thumbnail,
            "description": self.description,
            "extractor": self.extractor,
            "media_type": self.media_type,
            "labels": self.labels or {},
            "list_id": self.list_id,
            "downloaded": self.downloaded,
            "download_path": self.download_path,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
