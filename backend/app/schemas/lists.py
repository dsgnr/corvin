"""List schemas."""

from pydantic import BaseModel, Field


class ListPath(BaseModel):
    """List path parameter."""

    list_id: int = Field(..., description="List ID")


class ListQuery(BaseModel):
    """List query parameters."""

    include_videos: bool = Field(False, description="Include videos in response")
    include_stats: bool = Field(False, description="Include video statistics")


class ListTasksQuery(BaseModel):
    """Query parameters for list tasks and history."""

    limit: int | None = Field(100, description="Maximum number of results")


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


class ListResponse(BaseModel):
    """List response."""

    id: int
    name: str
    url: str
    list_type: str = "channel"
    extractor: str | None = None
    profile_id: int
    from_date: str | None = None
    sync_frequency: str = "daily"
    enabled: bool = True
    auto_download: bool = True
    last_synced: str | None = None
    next_sync_at: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    tags: list[str] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
