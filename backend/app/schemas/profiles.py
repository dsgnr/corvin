"""Profile schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DEFAULT_OUTPUT_TEMPLATE


class ProfileCreate(BaseModel):
    """Profile creation request."""

    name: str = Field(..., min_length=1, description="Profile name")
    output_template: str = Field(
        DEFAULT_OUTPUT_TEMPLATE,
        description="Output filename template",
    )
    embed_metadata: bool = Field(True, description="Embed metadata in file")
    embed_thumbnail: bool = Field(True, description="Embed thumbnail in file")
    include_shorts: bool = Field(True, description="Include YouTube Shorts")
    include_live: bool = Field(True, description="Include livestream recordings")
    download_subtitles: bool = Field(False, description="Download subtitles")
    embed_subtitles: bool = Field(False, description="Embed subtitles in file")
    auto_generated_subtitles: bool = Field(
        False, description="Include auto-generated subtitles"
    )
    subtitle_languages: str = Field(
        "en", description="Subtitle languages (comma-separated)"
    )
    audio_track_language: str | None = Field(
        "en", description="Preferred audio track language"
    )
    sponsorblock_behaviour: str = Field(
        "disabled", description="SponsorBlock behaviour"
    )
    sponsorblock_categories: list[str] = Field(
        default_factory=list, description="SponsorBlock categories"
    )
    output_format: str | None = Field(
        None,
        description="Output file format. For best results, leave this blank and the recommended container will be used (mp4)",
    )
    preferred_resolution: int | None = Field(
        None, description="Preferred video resolution height (e.g., 2160, 1080)"
    )
    preferred_video_codec: str | None = Field(
        None,
        description="Preferred video codec. Falls back to yt-dlp's default sorting if unavailable. See https://github.com/yt-dlp/yt-dlp#sorting-formats",
    )
    preferred_audio_codec: str | None = Field(
        None,
        description="Preferred audio codec. Falls back to yt-dlp's default sorting if unavailable. See https://github.com/yt-dlp/yt-dlp#sorting-formats",
    )
    extra_args: str = Field("{}", description="Extra yt-dlp arguments as JSON")


class ProfileUpdate(BaseModel):
    """Profile update request. All fields optional."""

    name: str | None = Field(None, min_length=1, description="Profile name")
    output_template: str | None = Field(None, description="Output filename template")
    embed_metadata: bool | None = Field(None, description="Embed metadata in file")
    embed_thumbnail: bool | None = Field(None, description="Embed thumbnail in file")
    include_shorts: bool | None = Field(None, description="Include YouTube Shorts")
    include_live: bool | None = Field(None, description="Include livestream recordings")
    download_subtitles: bool | None = Field(None, description="Download subtitles")
    embed_subtitles: bool | None = Field(None, description="Embed subtitles in file")
    auto_generated_subtitles: bool | None = Field(
        None, description="Include auto-generated subtitles"
    )
    subtitle_languages: str | None = Field(
        None, description="Subtitle languages (comma-separated)"
    )
    audio_track_language: str | None = Field(
        None, description="Preferred audio track language"
    )
    sponsorblock_behaviour: str | None = Field(
        None, description="SponsorBlock behaviour"
    )
    sponsorblock_categories: list[str] | None = Field(
        None, description="SponsorBlock categories"
    )
    output_format: str | None = Field(
        None,
        description="Output file format. For best results, leave this blank and the recommended container will be used (mp4)",
    )
    preferred_resolution: int | None = Field(
        None, description="Preferred video resolution height (e.g., 2160, 1080)"
    )
    preferred_video_codec: str | None = Field(
        None,
        description="Preferred video codec. Falls back to yt-dlp's default sorting if unavailable. See https://github.com/yt-dlp/yt-dlp#sorting-formats",
    )
    preferred_audio_codec: str | None = Field(
        None,
        description="Preferred audio codec. Falls back to yt-dlp's default sorting if unavailable. See https://github.com/yt-dlp/yt-dlp#sorting-formats",
    )
    extra_args: str | None = Field(None, description="Extra yt-dlp arguments as JSON")


class ProfileResponse(BaseModel):
    """Profile response matching Profile.to_dict() output."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    include_shorts: bool = True
    include_live: bool = True
    extra_args: str = "{}"
    download_subtitles: bool = False
    embed_subtitles: bool = False
    auto_generated_subtitles: bool = False
    subtitle_languages: str = "en"
    audio_track_language: str | None = "en"
    output_template: str = DEFAULT_OUTPUT_TEMPLATE
    sponsorblock_behaviour: str = "disabled"
    sponsorblock_categories: list[str] = []
    output_format: str | None
    preferred_resolution: int | None
    preferred_video_codec: str | None
    preferred_audio_codec: str | None
    created_at: str
    updated_at: str


class ProfileDefaults(BaseModel):
    """Default profile settings."""

    output_template: str
    embed_metadata: bool
    embed_thumbnail: bool
    include_shorts: bool
    include_live: bool
    download_subtitles: bool
    embed_subtitles: bool
    auto_generated_subtitles: bool
    subtitle_languages: str
    audio_track_language: str | None
    sponsorblock_behaviour: str
    sponsorblock_categories: list[str]
    output_format: str | None
    preferred_resolution: int | None
    preferred_video_codec: str | None
    preferred_audio_codec: str | None
    extra_args: str


class SponsorBlockOptions(BaseModel):
    """SponsorBlock configuration options."""

    behaviours: list[str]
    categories: list[str]
    category_labels: dict[str, str]


class ResolutionOption(BaseModel):
    """Resolution option with label and value."""

    label: str
    value: int


class CodecOption(BaseModel):
    """Codec option with label and value."""

    label: str
    value: str


class ProfileOptionsResponse(BaseModel):
    """Profile options and defaults."""

    defaults: ProfileDefaults
    sponsorblock: SponsorBlockOptions
    resolutions: list[ResolutionOption]
    video_codecs: list[CodecOption]
    audio_codecs: list[CodecOption]
