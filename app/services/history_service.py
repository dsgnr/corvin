import json

from app.extensions import db
from app.core.logging import get_logger
from app.models import History, HistoryAction

logger = get_logger("history")


class HistoryService:
    @staticmethod
    def log(
        action: HistoryAction,
        entity_type: str,
        entity_id: int | None = None,
        details: dict | None = None,
    ) -> History:
        """Log an action to history."""
        entry = History(
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details or {}),
        )
        db.session.add(entry)
        db.session.commit()

        logger.debug(
            "History: %s %s/%s %s",
            action.value,
            entity_type,
            entity_id,
            details,
        )
        return entry

    @staticmethod
    def get_all(
        limit: int = 100,
        offset: int = 0,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> list[History]:
        """Get history entries."""
        query = History.query.order_by(History.created_at.desc())

        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        if action:
            query = query.filter_by(action=action)

        return query.offset(offset).limit(limit).all()
