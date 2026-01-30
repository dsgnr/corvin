"""Video schemas."""

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    """Video response."""

    model_config = ConfigDict(from_attributes=True)

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
    filesize: int | None = None
    labels: dict = {}
    list_id: int
    downloaded: bool = False
    blacklisted: bool = False
    download_path: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: str
    updated_at: str


class VideoWithListResponse(VideoResponse):
    """Video response with embedded list info."""

    list: dict | None = None


class VideoRetryResponse(BaseModel):
    """Response for video retry operation."""

    message: str
    video: VideoResponse
