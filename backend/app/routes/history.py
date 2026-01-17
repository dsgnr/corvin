import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.extensions import SessionLocal, get_db
from app.models.history import History
from app.services import HistoryService

router = APIRouter(prefix="/api/history", tags=["History"])


def _get_history_fingerprint(entity_type: str | None, action: str | None) -> tuple:
    """Get fingerprint for change detection."""
    with SessionLocal() as db:
        q = db.query(func.count(History.id), func.max(History.created_at))
        if entity_type:
            q = q.filter(History.entity_type == entity_type)
        if action:
            q = q.filter(History.action == action)
        stats = q.first()
        return (stats[0], str(stats[1]) if stats[1] else None)


def _get_history_for_stream(
    entity_type: str | None, action: str | None, limit: int | None
) -> list[dict]:
    """Get history data optimised for SSE stream."""
    with SessionLocal() as db:
        entries = HistoryService.get_all(
            db,
            limit=limit,
            entity_type=entity_type,
            action=action,
        )
        return [e.to_dict() for e in entries]


@router.get("/")
async def get_history(
    request: Request,
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """Get history entries with optional filtering. Supports SSE streaming."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept:
        entries = HistoryService.get_all(
            db,
            limit=limit,
            offset=offset,
            entity_type=entity_type,
            action=action,
        )
        return [e.to_dict() for e in entries]

    # SSE stream
    async def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            fingerprint = _get_history_fingerprint(entity_type, action)

            if fingerprint != last_fingerprint:
                data = _get_history_for_stream(entity_type, action, limit)
                yield {"data": json.dumps(data, default=str)}
                last_fingerprint = fingerprint
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= 30:
                    yield {"comment": "heartbeat"}
                    heartbeat_counter = 0

            await asyncio.sleep(1)

    return EventSourceResponse(generate())
