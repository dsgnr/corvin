"""History schemas."""

from pydantic import BaseModel


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
