from datetime import datetime

from app.extensions import db


class Profile(db.Model):
    """yt-dlp download profile with quality and format settings."""

    __tablename__ = "profiles"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False, unique=True)
    sponsorblock_remove: str = db.Column(db.String(200), default="")
    embed_metadata: bool = db.Column(db.Boolean, default=True)
    embed_thumbnail: bool = db.Column(db.Boolean, default=False)
    extra_args: str = db.Column(db.Text, default="{}")
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sponsorblock_remove": self.sponsorblock_remove,
            "embed_metadata": self.embed_metadata,
            "embed_thumbnail": self.embed_thumbnail,
            "extra_args": self.extra_args,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_yt_dlp_opts(self) -> dict:
        """Convert profile settings to yt-dlp options dict."""
        opts = {
            "writethumbnail": self.embed_thumbnail,
            "embedmetadata": self.embed_metadata,
        }
        if self.sponsorblock_remove:
            opts["sponsorblock_remove"] = self.sponsorblock_remove.split(",")
        return opts
