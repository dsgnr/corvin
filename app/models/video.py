from datetime import datetime

from app.extensions import db


class Video(db.Model):
    """An individual video discovered from a list."""

    __tablename__ = "videos"

    id: int = db.Column(db.Integer, primary_key=True)
    video_id: str = db.Column(db.String(50), nullable=False)
    title: str = db.Column(db.String(500), nullable=False)
    url: str = db.Column(db.String(500), nullable=False)
    duration: int | None = db.Column(db.Integer, nullable=True)
    upload_date: datetime | None = db.Column(db.DateTime, nullable=True)
    thumbnail: str | None = db.Column(db.String(500), nullable=True)
    list_id: int = db.Column(
        db.Integer, db.ForeignKey("video_lists.id"), nullable=False
    )
    downloaded: bool = db.Column(db.Boolean, default=False)
    download_path: str | None = db.Column(db.String(500), nullable=True)
    error_message: str | None = db.Column(db.Text, nullable=True)
    retry_count: int = db.Column(db.Integer, default=0)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    video_list = db.relationship("VideoList", back_populates="videos")

    __table_args__ = (db.UniqueConstraint("video_id", "list_id", name="uq_video_list"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "duration": self.duration,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "thumbnail": self.thumbnail,
            "list_id": self.list_id,
            "downloaded": self.downloaded,
            "download_path": self.download_path,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
