"""History schemas."""

from pydantic import BaseModel, Field

from app.schemas.common import PaginationQuery


class HistoryQuery(PaginationQuery):
    """History query parameters."""

    entity_type: str | None = Field(None, description="Filter by entity type")
    action: str | None = Field(None, description="Filter by action")


class HistoryResponse(BaseModel):
    """History entry response."""

    id: int
    action: str
    entity_type: str
    entity_id: int | None = None
    details: str = "{}"
    created_at: str

    class Config:
        from_attributes = True
