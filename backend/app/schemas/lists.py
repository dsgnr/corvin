"""List schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.history import HistoryResponse
from app.schemas.tasks import ActiveTasksResponse


class ListCreate(BaseModel):
    """List creation request."""

    name: str = Field(..., min_length=1, description="List name")
    url: str = Field(..., description="Channel/playlist URL")
    profile_id: int = Field(..., description="Profile ID to use")
    list_type: str = Field("channel", description="Type: channel or playlist")
    from_date: str | None = Field(
        None, description="Only sync videos after this date (YYYYMMDD)"
    )
    sync_frequency: str = Field("daily", description="Sync frequency")
    enabled: bool = Field(True, description="Enable automatic syncing")
    auto_download: bool = Field(True, description="Auto-download new videos")
    blacklist_regex: str | None = Field(
        None, description="Regex pattern to blacklist videos by title"
    )
    min_duration: int | None = Field(
        None, description="Minimum video duration in seconds"
    )
    max_duration: int | None = Field(
        None, description="Maximum video duration in seconds"
    )


class BulkListCreate(BaseModel):
    """Bulk list creation request."""

    urls: list[str] = Field(..., min_length=1, description="List of URLs to add")
    profile_id: int = Field(..., description="Profile ID to use for all lists")
    list_type: str = Field("channel", description="Type: channel or playlist")
    sync_frequency: str = Field("daily", description="Sync frequency")
    enabled: bool = Field(True, description="Enable automatic syncing")
    auto_download: bool = Field(True, description="Auto-download new videos")
    from_date: str | None = Field(
        None, description="Only sync videos after this date (YYYYMMDD)"
    )
    blacklist_regex: str | None = Field(
        None, description="Regex pattern to blacklist videos by title"
    )
    min_duration: int | None = Field(
        None, description="Minimum video duration in seconds"
    )
    max_duration: int | None = Field(
        None, description="Maximum video duration in seconds"
    )


class BulkListResponse(BaseModel):
    """Bulk list creation response."""

    created: list["ListResponse"] = []
    errors: list[dict] = []


class ListUpdate(BaseModel):
    """List update request. All fields optional."""

    name: str | None = Field(None, min_length=1, description="List name")
    url: str | None = Field(None, description="Channel/playlist URL")
    profile_id: int | None = Field(None, description="Profile ID to use")
    list_type: str | None = Field(None, description="Type: channel or playlist")
    from_date: str | None = Field(
        None, description="Only sync videos after this date (YYYYMMDD)"
    )
    sync_frequency: str | None = Field(None, description="Sync frequency")
    enabled: bool | None = Field(None, description="Enable automatic syncing")
    auto_download: bool | None = Field(None, description="Auto-download new videos")
    blacklist_regex: str | None = Field(
        None, description="Regex pattern to blacklist videos by title"
    )
    min_duration: int | None = Field(
        None, description="Minimum video duration in seconds"
    )
    max_duration: int | None = Field(
        None, description="Maximum video duration in seconds"
    )


class ListResponse(BaseModel):
    """List response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_name: str | None = None
    url: str
    list_type: str = "channel"
    extractor: str | None = None
    profile_id: int
    from_date: str | None = None
    sync_frequency: str = "daily"
    enabled: bool = True
    auto_download: bool = True
    blacklist_regex: str | None = None
    min_duration: int | None = None
    max_duration: int | None = None
    deleting: bool = False
    last_synced: str | None = None
    next_sync_at: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    tags: list[str] = []
    created_at: str
    updated_at: str


class VideoStatsResponse(BaseModel):
    """Video statistics for a list."""

    total: int
    downloaded: int
    failed: int
    pending: int
    blacklisted: int = 0
    newest_id: int | None = None
    last_updated: str | None = None


class ListVideoStatsResponse(BaseModel):
    """Combined stats and active tasks for a list."""

    stats: VideoStatsResponse
    tasks: ActiveTasksResponse
    changed_video_ids: list[int] = []


class VideoSummary(BaseModel):
    """Minimal video info for list views."""

    id: int
    video_id: str
    title: str
    duration: int | None = None
    upload_date: str | None = None
    media_type: str = "video"
    thumbnail: str | None = None
    downloaded: bool = False
    blacklisted: bool = False
    error_message: str | None = None
    labels: dict = {}


class VideosPaginatedResponse(BaseModel):
    """Paginated videos response."""

    videos: list[VideoSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class HistoryPaginatedResponse(BaseModel):
    """Paginated history response for a list."""

    entries: list[HistoryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
