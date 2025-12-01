from flask import Blueprint, request, jsonify

from app.services import HistoryService

bp = Blueprint("history", __name__, url_prefix="/api/history")


@bp.get("/")
def get_history():
    """Get history entries with optional filtering."""
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    entity_type = request.args.get("entity_type")
    action = request.args.get("action")

    entries = HistoryService.get_all(
        limit=limit,
        offset=offset,
        entity_type=entity_type,
        action=action,
    )
    return jsonify([e.to_dict() for e in entries])
