"""Task schemas."""

from pydantic import BaseModel, ConfigDict, Field


class TaskResponse(BaseModel):
    """Task response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_type: str
    entity_id: int
    entity_name: str | None = None
    status: str = "pending"
    result: str | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class TaskLogResponse(BaseModel):
    """Task log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt: int
    level: str = "info"
    message: str
    created_at: str


class WorkerStats(BaseModel):
    """Worker statistics."""

    running: bool
    paused_sync: bool
    paused_download: bool
    current_task_id: int | None = None
    current_task_type: str | None = None


class TaskStatsResponse(BaseModel):
    """Task statistics response."""

    pending_sync: int
    pending_download: int
    running_sync: int
    running_download: int
    worker: WorkerStats | None = None


class TaskStatusList(BaseModel):
    """List of entity IDs by status."""

    pending: list[int] = []
    running: list[int] = []


class ActiveTasksResponse(BaseModel):
    """Active tasks response."""

    sync: TaskStatusList
    download: TaskStatusList


class TasksPaginatedResponse(BaseModel):
    """Paginated tasks response."""

    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


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
