"""
History routes.
"""

from fastapi import APIRouter, Query, Request

from app.extensions import ReadSessionLocal
from app.models.history import History
from app.schemas.lists import HistoryPaginatedResponse
from app.sse_hub import Channel
from app.sse_stream import sse_response, wants_sse

router = APIRouter(prefix="/api/history", tags=["History"])


def _fetch_history_paginated(
    entity_type: str | None,
    action: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    """Fetch paginated history entries."""
    with ReadSessionLocal() as db:
        base_query = db.query(History)
        if entity_type:
            base_query = base_query.filter(History.entity_type == entity_type)
        if action:
            base_query = base_query.filter(History.action == action)
        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.filter(
                (History.action.ilike(search_pattern))
                | (History.entity_type.ilike(search_pattern))
                | (History.details.ilike(search_pattern))
            )

        total = base_query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)

        entries = (
            base_query.order_by(History.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "entries": [entry.to_dict() for entry in entries],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


@router.get("", response_model=HistoryPaginatedResponse)
async def get_history(
    request: Request,
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get history entries with optional filtering and pagination.

    Supports two modes:
    - Regular JSON response for standard requests (with pagination)
    - Server-Sent Events (SSE) stream for real-time updates when Accept header
      includes 'text/event-stream'
    """
    if not wants_sse(request):
        return _fetch_history_paginated(entity_type, action, search, page, page_size)

    return sse_response(
        request,
        Channel.HISTORY,
        lambda: _fetch_history_paginated(entity_type, action, search, page, page_size),
    )
