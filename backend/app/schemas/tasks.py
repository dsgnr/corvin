"""Task schemas."""

from pydantic import BaseModel, Field

from app.schemas.common import PaginationQuery


class TaskPath(BaseModel):
    """Task path parameter."""

    task_id: int = Field(..., description="Task ID")


class ListIdPath(BaseModel):
    """List ID path parameter."""

    list_id: int = Field(..., description="List ID")


class VideoIdPath(BaseModel):
    """Video ID path parameter."""

    video_id: int = Field(..., description="Video ID")


class TaskQuery(PaginationQuery):
    """Task query parameters."""

    type: str | None = Field(None, description="Filter by task type (sync, download)")
    status: str | None = Field(
        None, description="Filter by status (pending, running, completed, failed)"
    )


class TaskLogsQuery(BaseModel):
    """Task logs query parameters."""

    include_logs: bool = Field(True, description="Include task logs")


class ActiveTasksQuery(BaseModel):
    """Active tasks query parameters."""

    list_id: int | None = Field(None, description="Filter by list ID")


class TaskResponse(BaseModel):
    """Task response."""

    id: int
    task_type: str
    entity_id: int
    entity_name: str | None = None
    status: str = "pending"
    result: str | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None

    class Config:
        from_attributes = True


class TaskLogResponse(BaseModel):
    """Task log response."""

    id: int
    attempt: int
    level: str = "info"
    message: str
    created_at: str

    class Config:
        from_attributes = True


class TaskStatsResponse(BaseModel):
    """Task statistics response."""

    pending_sync: int
    pending_download: int
    running_sync: int
    running_download: int
    worker: dict | None = None


class ActiveTasksResponse(BaseModel):
    """Active tasks response."""

    sync: dict
    download: dict


class BulkSyncRequest(BaseModel):
    """Bulk sync request."""

    list_ids: list[int] = Field(..., min_length=1, description="List IDs to sync")


class BulkDownloadRequest(BaseModel):
    """Bulk download request."""

    video_ids: list[int] = Field(..., min_length=1, description="Video IDs to download")


class BulkTaskIdsRequest(BaseModel):
    """Bulk task IDs request."""

    task_ids: list[int] = Field(..., min_length=1, description="Task IDs to operate on")


class BulkResultResponse(BaseModel):
    """Bulk operation result."""

    queued: int
    skipped: int


class BulkTaskResultResponse(BaseModel):
    """Bulk task operation result."""

    affected: int
    skipped: int
