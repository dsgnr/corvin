"""Common schemas."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class AffectedResponse(BaseModel):
    """Response for bulk operations that affect rows."""

    affected: int


class PausedResponse(BaseModel):
    """Response for pause/resume operations."""

    affected: int
    paused: bool


class DeletionStartedResponse(BaseModel):
    """Response when deletion is started in background."""

    message: str
