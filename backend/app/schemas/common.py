"""Common schemas."""

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class PaginationQuery(BaseModel):
    """Common pagination parameters."""

    limit: int | None = Field(
        None, ge=1, description="Maximum items to return (None = all)"
    )
    offset: int = Field(0, ge=0, description="Number of items to skip")
