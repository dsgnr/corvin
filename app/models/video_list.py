from datetime import datetime, date

from app.extensions import db


class VideoList(db.Model):
    """A channel or playlist to monitor for videos."""

    __tablename__ = "video_lists"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(200), nullable=False)
    url: str = db.Column(db.String(500), nullable=False, unique=True)
    list_type: str = db.Column(db.String(20), default="channel")
    profile_id: int = db.Column(
        db.Integer, db.ForeignKey("profiles.id"), nullable=False
    )
    from_date: date | None = db.Column(db.Date, nullable=True)
    enabled: bool = db.Column(db.Boolean, default=True)
    last_synced: datetime | None = db.Column(db.DateTime, nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profile = db.relationship("Profile", back_populates="lists")
    videos = db.relationship(
        "Video", back_populates="video_list", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self, include_videos: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "list_type": self.list_type,
            "profile_id": self.profile_id,
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "enabled": self.enabled,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_videos:
            data["videos"] = [v.to_dict() for v in self.videos]
        return data
