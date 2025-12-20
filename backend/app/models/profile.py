from datetime import datetime

from app.extensions import db


class SponsorBlockBehavior:
    """SponsorBlock behavior options."""
    DISABLED = "disabled"
    DELETE = "delete"
    MARK_CHAPTER = "mark_chapter"

    ALL = [DISABLED, DELETE, MARK_CHAPTER]


# Valid SponsorBlock categories
SPONSORBLOCK_CATEGORIES = [
    "sponsor",           # Sponsor
    "intro",             # Intro/Intermission
    "outro",             # Outro/Credits
    "selfpromo",         # Unpaid/Self Promotion
    "preview",           # Preview/Recap
    "interaction",       # Interaction Reminder (Subscribe)
    "music_offtopic",    # Music: Non-Music Section
    "filler",            # Tangents/Jokes
]

# Supported output formats for remuxing
OUTPUT_FORMATS = ["3gp", "aac", "flv", "m4a", "mp3", "mp4", "ogg", "wav", "webm"]


class Profile(db.Model):
    """yt-dlp download profile with quality and format settings."""

    __tablename__ = "profiles"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False, unique=True)
    embed_metadata: bool = db.Column(db.Boolean, default=True)
    embed_thumbnail: bool = db.Column(db.Boolean, default=True)
    exclude_shorts: bool = db.Column(db.Boolean, default=False)
    extra_args: str = db.Column(db.Text, default="{}")

    # Subtitle options
    download_subtitles: bool = db.Column(db.Boolean, default=False)
    embed_subtitles: bool = db.Column(db.Boolean, default=False)
    auto_generated_subtitles: bool = db.Column(db.Boolean, default=False)
    subtitle_languages: str = db.Column(db.String(200), default="en")

    # Audio track language
    audio_track_language: str = db.Column(db.String(100), default="en")

    # Output path template
    output_template: str = db.Column(db.String(500), default="%(uploader)s/s%(upload_date>%Y)se%(upload_date>%m%d)s - %(title)s.%(ext)s")

    # SponsorBlock options
    sponsorblock_behavior: str = db.Column(db.String(20), default=SponsorBlockBehavior.DISABLED)
    sponsorblock_categories: str = db.Column(db.String(500), default="")

    # Output format for remuxing
    output_format: str = db.Column(db.String(20), default="mp4")

    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    lists = db.relationship("VideoList", back_populates="profile", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "embed_metadata": self.embed_metadata,
            "embed_thumbnail": self.embed_thumbnail,
            "exclude_shorts": self.exclude_shorts,
            "extra_args": self.extra_args,
            # Subtitle options
            "download_subtitles": self.download_subtitles,
            "embed_subtitles": self.embed_subtitles,
            "auto_generated_subtitles": self.auto_generated_subtitles,
            "subtitle_languages": self.subtitle_languages,
            # Audio track language
            "audio_track_language": self.audio_track_language,
            # Output template
            "output_template": self.output_template,
            # SponsorBlock options
            "sponsorblock_behavior": self.sponsorblock_behavior,
            "sponsorblock_categories": self.sponsorblock_categories,
            # Output format
            "output_format": self.output_format,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_yt_dlp_opts(self) -> dict:
        """Convert profile settings to a yt-dlp options dictionary."""
        output_fmt = self.output_format if self.output_format in OUTPUT_FORMATS else "mp4"

        opts = {
            "paths": {"temp": "/tmp"},
            "fragment_retries": 10,
            "retries": 10,
            "final_ext": output_fmt,
            "merge_output_format": output_fmt,
            "format_sort": ["vcodec:h264", "lang", "quality", "res", "fps", "hdr:12", "acodec:aac"],
        }

        postprocessors = []
        self._add_metadata_postprocessors(opts, postprocessors)
        self._add_subtitle_postprocessors(opts, postprocessors)
        self._add_audio_options(opts)
        self._add_sponsorblock_postprocessors(postprocessors)
        self._add_output_postprocessors(postprocessors, output_fmt)

        opts["postprocessors"] = postprocessors
        return opts

    def _add_metadata_postprocessors(self, opts: dict, postprocessors: list) -> None:
        """Add metadata and thumbnail postprocessors."""
        if self.embed_metadata:
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_chapters": True,
                "add_infojson": "if_exists",
                "add_metadata": True,
            })

        if self.embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append({
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
                "when": "before_dl",
            })
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": True,
            })

    def _add_subtitle_postprocessors(self, opts: dict, postprocessors: list) -> None:
        """Add subtitle-related options and postprocessors."""
        if self.download_subtitles or self.embed_subtitles:
            opts["writesubtitles"] = True
            opts["subtitlesformat"] = "srt"
            if self.subtitle_languages:
                opts["subtitleslangs"] = [lang.strip() for lang in self.subtitle_languages.split(",")]

        if self.download_subtitles:
            postprocessors.append({
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
                "when": "before_dl",
            })

        if self.auto_generated_subtitles:
            opts["writeautomaticsub"] = True
            opts["subtitlesformat"] = "srt"

        if self.embed_subtitles:
            postprocessors.append({
                "key": "FFmpegEmbedSubtitle",
                "already_have_subtitle": True,
            })

    def _add_audio_options(self, opts: dict) -> None:
        """Add audio track language preferences."""
        if self.audio_track_language:
            opts["audio_multistreams"] = True
            opts["format_sort"] = [f"lang:{self.audio_track_language}"] + opts["format_sort"]

    def _add_sponsorblock_postprocessors(self, postprocessors: list) -> None:
        """Add SponsorBlock postprocessors if enabled."""
        if self.sponsorblock_behavior == SponsorBlockBehavior.DISABLED:
            return
        if not self.sponsorblock_categories:
            return

        categories = [c.strip() for c in self.sponsorblock_categories.split(",") if c.strip()]
        if not categories:
            return

        categories_set = set(categories)

        postprocessors.append({
            "key": "SponsorBlock",
            "api": "https://sponsor.ajay.app",
            "categories": categories_set,
            "when": "after_filter",
        })

        remove_segments = categories_set if self.sponsorblock_behavior == SponsorBlockBehavior.DELETE else set()
        postprocessors.append({
            "key": "ModifyChapters",
            "force_keyframes": False,
            "remove_chapters_patterns": [],
            "remove_ranges": [],
            "remove_sponsor_segments": remove_segments,
            "sponsorblock_chapter_title": "[SponsorBlock]: %(category_names)l",
        })

        if self.sponsorblock_behavior == SponsorBlockBehavior.MARK_CHAPTER:
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_chapters": True,
                "add_infojson": None,
                "add_metadata": False,
            })

    def _add_output_postprocessors(self, postprocessors: list, output_fmt: str) -> None:
        """Add output format remuxing postprocessors."""
        postprocessors.append({
            "key": "FFmpegVideoRemuxer",
            "preferedformat": output_fmt,
        })
        postprocessors.append({
            "key": "FFmpegConcat",
            "only_multi_video": True,
            "when": "playlist",
        })
