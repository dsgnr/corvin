import json
import time

from flask import Response, current_app, jsonify, request
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import func

from app.extensions import db
from app.models.history import History
from app.schemas.history import HistoryQuery
from app.services import HistoryService

tag = Tag(name="History", description="Activity history")
bp = APIBlueprint("history", __name__, url_prefix="/api/history", abp_tags=[tag])


def _get_history_fingerprint(entity_type: str | None, action: str | None) -> tuple:
    """Get fingerprint for change detection."""
    q = db.session.query(func.count(History.id), func.max(History.created_at))
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
    entries = HistoryService.get_all(
        limit=limit,
        entity_type=entity_type,
        action=action,
    )
    return [e.to_dict() for e in entries]


@bp.get("/")
def get_history(query: HistoryQuery):
    """Get history entries with optional filtering.

    If Accept header is 'text/event-stream', streams updates via SSE.
    Otherwise returns JSON array of history entries.
    """
    # Regular JSON response (early return)
    if request.accept_mimetypes.best != "text/event-stream":
        entries = HistoryService.get_all(
            limit=query.limit,
            offset=query.offset,
            entity_type=query.entity_type,
            action=query.action,
        )
        return jsonify([e.to_dict() for e in entries])

    # SSE stream
    app = current_app._get_current_object()
    entity_type = query.entity_type
    action = query.action
    limit = query.limit

    def generate():
        last_fingerprint = None
        heartbeat_counter = 0

        while True:
            with app.app_context():
                fingerprint = _get_history_fingerprint(entity_type, action)

                if fingerprint != last_fingerprint:
                    data = _get_history_for_stream(entity_type, action, limit)
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                    last_fingerprint = fingerprint
                    heartbeat_counter = 0
                else:
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:
                        yield ": heartbeat\n\n"
                        heartbeat_counter = 0

            time.sleep(1)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
