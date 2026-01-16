from app.core.logging import get_logger
from app.extensions import db
from app.models import History, HistoryAction

logger = get_logger("history")


class HistoryService:
    @staticmethod
    def log(
        action: HistoryAction,
        entity_type: str,
        entity_id: int | None = None,
        details: dict | None = None,
        commit: bool = True,
    ) -> History:
        """Log an action to history."""
        entry = History(
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        db.session.add(entry)
        if commit:
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
        limit: int | None = None,
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

        query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()
