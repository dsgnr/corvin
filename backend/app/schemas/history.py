"""History schemas."""

from typing import Any

from pydantic import BaseModel


class HistoryResponse(BaseModel):
    """History entry response."""

    id: int
    action: str
    entity_type: str
    entity_id: int | None = None
    details: dict[str, Any] = {}
    created_at: str

    class Config:
        from_attributes = True
