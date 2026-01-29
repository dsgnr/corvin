"""Settings schemas."""

from pydantic import BaseModel, Field


class DataRetentionResponse(BaseModel):
    """Data retention settings response."""

    retention_days: int = Field(
        description="Number of days to retain data (0 = disabled)"
    )


class DataRetentionUpdate(BaseModel):
    """Data retention settings update."""

    retention_days: int = Field(
        ge=0,
        le=365,
        description="Number of days to retain data (0 = disabled, max 1 year)",
    )


class VacuumResponse(BaseModel):
    """Response from database vacuum operation."""

    success: bool = Field(description="Whether the vacuum operation succeeded")
    message: str = Field(description="Status message")
    size_before: int | None = Field(
        default=None, description="Database size in bytes before vacuum"
    )
    size_after: int | None = Field(
        default=None, description="Database size in bytes after vacuum"
    )
    space_reclaimed: int | None = Field(
        default=None, description="Bytes reclaimed by vacuum"
    )
