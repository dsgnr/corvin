"""Video schemas."""

from pydantic import BaseModel, Field

from app.schemas.common import PaginationQuery


class VideoPath(BaseModel):
    """Video path parameter."""

    video_id: int = Field(..., description="Video ID")


class VideoListPath(BaseModel):
    """Video list path parameter for videos endpoint."""

    list_id: int = Field(..., description="List ID")


class VideoQuery(PaginationQuery):
    """Video query parameters."""

    list_id: int | None = Field(None, description="Filter by list ID")
    downloaded: bool | None = Field(None, description="Filter by download status")


class VideoResponse(BaseModel):
    """Video response."""

    id: int
    video_id: str
    title: str
    url: str
    duration: int | None = None
    upload_date: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    extractor: str | None = None
    media_type: str = "video"
    labels: dict = {}
    list_id: int
    downloaded: bool = False
    download_path: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
