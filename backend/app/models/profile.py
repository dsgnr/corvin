"""
Profile model for yt-dlp download configuration.
Profiles define how videos are downloaded.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.constants import (
    DEFAULT_OUTPUT_TEMPLATE,
    RESOLUTION_MAP,
    SPONSORBLOCK_DELETE,
    SPONSORBLOCK_DISABLED,
    SPONSORBLOCK_MARK_CHAPTER,
)
from app.models import Base


class Profile(Base):
    """
    yt-dlp download profile.

    Each VideoList references a Profile that determines how its videos
    are downloaded. Multiple lists can share the same profile.
    """

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    embed_metadata = Column(Boolean, default=True)
    embed_thumbnail = Column(Boolean, default=True)
    include_shorts = Column(Boolean, default=True)
    include_live = Column(Boolean, default=True)
    extra_args = Column(JSON, default=dict)

    # Subtitle options
    download_subtitles = Column(Boolean, default=False)
    embed_subtitles = Column(Boolean, default=False)
    auto_generated_subtitles = Column(Boolean, default=False)
    subtitle_languages = Column(String(200), default="en")

    # Audio track language
    audio_track_language = Column(String(100))

    # Output path template
    output_template = Column(
        String(500),
        default=DEFAULT_OUTPUT_TEMPLATE,
    )

    # SponsorBlock options
    sponsorblock_behaviour = Column(String(20), default=SPONSORBLOCK_DISABLED)
    sponsorblock_categories = Column(JSON, default=list)

    # Output format for remuxing
    output_format = Column(String(4))

    # Preferred resolution (height in pixels, e.g., 2160, 1080)
    preferred_resolution = Column(Integer)

    # Codec preferences
    preferred_video_codec = Column(String(10))
    preferred_audio_codec = Column(String(10))

    # Filename restrictions
    windows_filenames = Column(Boolean, default=False)
    restrict_filenames = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lists = relationship("VideoList", back_populates="profile", lazy="dynamic")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialisation."""
        return {
            "id": self.id,
            "name": self.name,
            "embed_metadata": self.embed_metadata,
            "embed_thumbnail": self.embed_thumbnail,
            "include_shorts": self.include_shorts,
            "include_live": self.include_live,
            "extra_args": self.extra_args or {},
            "download_subtitles": self.download_subtitles,
            "embed_subtitles": self.embed_subtitles,
            "auto_generated_subtitles": self.auto_generated_subtitles,
            "subtitle_languages": self.subtitle_languages,
            "audio_track_language": self.audio_track_language,
            "output_template": self.output_template,
            "sponsorblock_behaviour": self.sponsorblock_behaviour,
            "sponsorblock_categories": self.sponsorblock_categories or [],
            "output_format": self.output_format,
            "preferred_resolution": self.preferred_resolution,
            "preferred_video_codec": self.preferred_video_codec,
            "preferred_audio_codec": self.preferred_audio_codec,
            "windows_filenames": self.windows_filenames,
            "restrict_filenames": self.restrict_filenames,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_yt_dlp_opts(self) -> dict:
        """
        Convert profile settings to a yt-dlp options dictionary.

        Returns:
            Dictionary of yt-dlp options ready for use with YoutubeDL.
        """
        is_audio_only = self.preferred_resolution == 0

        # Base options shared by both modes
        opts = {
            "paths": {"temp": "/tmp"},
            "fragment_retries": 10,
            "retries": 10,
        }

        # Filename restrictions
        if self.windows_filenames:
            opts["windowsfilenames"] = True
        if self.restrict_filenames:
            opts["restrictfilenames"] = True

        postprocessors = []

        if is_audio_only:
            opts["format"] = "bestaudio/best"
            opts["final_ext"] = "m4a"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "nopostoverwrites": False,
                    "preferredcodec": "m4a",
                    "preferredquality": "5",
                }
            )
        else:
            opts["audio_multistreams"] = True
            # Default to mp4 for better metadata compatibility with media servers
            opts["merge_output_format"] = self.output_format or "mp4"

            # Only add format_sort if video codec preference is set
            if self.preferred_video_codec:
                opts["format_sort"] = [f"vcodec:{self.preferred_video_codec}"]

            opts["format"] = self._build_format_string()

            # Video-only postprocessors
            self._add_subtitle_postprocessors(opts, postprocessors)
            self._add_audio_options(opts)
            self._add_output_postprocessors(postprocessors)

        # Shared postprocessors for both modes
        self._add_metadata_postprocessors(opts, postprocessors)
        self._add_sponsorblock_postprocessors(postprocessors)

        opts["postprocessors"] = postprocessors

        # Merge extra_args (only adds new keys, won't overwrite existing)
        self._merge_extra_args(opts)

        return opts

    def _merge_extra_args(self, opts: dict) -> None:
        """
        Merge extra_args into opts without overwriting existing keys.

        Only top-level keys that don't already exist in opts are added.
        This ensures profile settings take precedence over extra_args.
        """
        if not self.extra_args:
            return

        if not isinstance(self.extra_args, dict):
            return

        for key, value in self.extra_args.items():
            if key not in opts:
                opts[key] = value

    def _build_format_string(self) -> str:
        """
        Build yt-dlp format string based on profile preferences.

        Priority: language + codec > language only > codec only > any
        """
        audio_codec = self.preferred_audio_codec or "opus"
        audio_lang = self.audio_track_language
        res = self.preferred_resolution

        # Build video selector
        video = "bv*"
        fallback = "best"
        if res and res in RESOLUTION_MAP:
            video = f"bv*[height<={res}]"
            fallback = f"best[height<={res}]"

        # Build audio selectors in priority order
        audio_filters = []
        if audio_lang:
            audio_filters.append(f"ba[language={audio_lang}][acodec={audio_codec}]")
            audio_filters.append(f"ba[language={audio_lang}]")
        audio_filters.append(f"ba[acodec={audio_codec}]")
        audio_filters.append("ba")

        # Combine into format string with fallbacks
        formats = [f"{video}+{af}" for af in audio_filters]
        formats.append(fallback)
        return "/".join(formats)

    def _add_date_metadata_parser(self, postprocessors: list) -> None:
        """
        Add MetadataParser to extract upload_date into meta_date field.

        `date` in the metadata is returned as YYYYMMDD, but Plex wants YYYY-MM-DD
        or the "Originally Available" value is in 1969.
        """
        from yt_dlp.postprocessor.metadataparser import MetadataParserPP

        postprocessors.append(
            {
                "key": "MetadataParser",
                "actions": [
                    (
                        MetadataParserPP.interpretter,
                        "%(upload_date>%Y-%m-%d|)s",
                        "%(meta_date)s",
                    )
                ],
                "when": "pre_process",
            }
        )

    def _add_metadata_postprocessors(self, opts: dict, postprocessors: list) -> None:
        """Add metadata and thumbnail postprocessors."""
        if self.embed_metadata:
            postprocessors.append(
                {
                    "key": "FFmpegMetadata",
                    "add_chapters": True,
                    "add_infojson": "if_exists",
                    "add_metadata": True,
                }
            )

        if self.embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append(
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                    "when": "before_dl",
                }
            )
            postprocessors.append(
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": True,
                }
            )
        self._add_date_metadata_parser(postprocessors)

    def _add_subtitle_postprocessors(self, opts: dict, postprocessors: list) -> None:
        """Add subtitle options and postprocessors."""
        if self.download_subtitles or self.embed_subtitles:
            opts["writesubtitles"] = True
            opts["subtitlesformat"] = "srt"
            if self.subtitle_languages:
                opts["subtitleslangs"] = [
                    lang.strip() for lang in self.subtitle_languages.split(",")
                ]

        if self.download_subtitles:
            postprocessors.append(
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                    "when": "before_dl",
                }
            )

        if self.auto_generated_subtitles:
            opts["writeautomaticsub"] = True
            opts["subtitlesformat"] = "srt"

        if self.embed_subtitles:
            postprocessors.append(
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": True,
                }
            )

    def _add_audio_options(self, opts: dict) -> None:
        """Add audio multistreams option."""
        # Language preference is handled in the format string for reliability
        opts["audio_multistreams"] = True

    def _add_sponsorblock_postprocessors(self, postprocessors: list) -> None:
        """Add SponsorBlock postprocessors if enabled."""
        if self.sponsorblock_behaviour == SPONSORBLOCK_DISABLED:
            return
        if not self.sponsorblock_categories:
            return

        postprocessors.append(
            {
                "key": "SponsorBlock",
                "api": "https://sponsor.ajay.app",
                "categories": self.sponsorblock_categories,
                "when": "after_filter",
            }
        )

        remove_segments = (
            self.sponsorblock_categories
            if self.sponsorblock_behaviour == SPONSORBLOCK_DELETE
            else []
        )
        postprocessors.append(
            {
                "key": "ModifyChapters",
                "force_keyframes": False,
                "remove_chapters_patterns": [],
                "remove_ranges": [],
                "remove_sponsor_segments": remove_segments,
                "sponsorblock_chapter_title": "[SponsorBlock]: %(category_names)l",
            }
        )

        if self.sponsorblock_behaviour == SPONSORBLOCK_MARK_CHAPTER:
            postprocessors.append(
                {
                    "key": "FFmpegMetadata",
                    "add_chapters": True,
                    "add_infojson": "if_exists",
                    "add_metadata": True,
                }
            )

    def _add_output_postprocessors(self, postprocessors: list) -> None:
        """Add output format remuxing postprocessors."""
        postprocessors.append(
            {
                "key": "FFmpegConcat",
                "only_multi_video": True,
                "when": "playlist",
            }
        )
