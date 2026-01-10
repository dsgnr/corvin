"""Common schemas."""

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class PaginationQuery(BaseModel):
    """Common pagination parameters."""

    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
