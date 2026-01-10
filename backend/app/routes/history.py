from flask import jsonify
from flask_openapi3 import APIBlueprint, Tag

from app.schemas.history import HistoryQuery
from app.services import HistoryService

tag = Tag(name="History", description="Activity history")
bp = APIBlueprint("history", __name__, url_prefix="/api/history", abp_tags=[tag])


@bp.get("/")
def get_history(query: HistoryQuery):
    """Get history entries with optional filtering."""
    offset = (query.page - 1) * query.per_page
    entries = HistoryService.get_all(
        limit=query.per_page,
        offset=offset,
        entity_type=query.entity_type,
        action=query.action,
    )
    return jsonify([e.to_dict() for e in entries])
