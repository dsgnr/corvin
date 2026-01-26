"""
History service for audit logging.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import History, HistoryAction

logger = get_logger("history")


class HistoryService:
    """Service for logging actions to the history table."""

    @staticmethod
    def log(
        db: Session,
        action: HistoryAction,
        entity_type: str,
        entity_id: int | None = None,
        details: dict | None = None,
        commit: bool = True,
    ) -> History:
        """
        Log an action to history.

        Args:
            db: Database session.
            action: The action being logged.
            entity_type: Type of entity (e.g., "list", "video", "profile").
            entity_id: ID of the affected entity, or None.
            details: Additional details as a dictionary.
            commit: Whether to commit the transaction.

        Returns:
            The created History entry.
        """
        entry = History(
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        db.add(entry)
        if commit:
            db.commit()

        from app.sse_hub import Channel, broadcast

        broadcast(Channel.HISTORY)

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
        db: Session,
        limit: int | None = None,
        offset: int = 0,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> list[History]:
        """
        Get history entries with optional filtering.

        Args:
            db: Database session.
            limit: Maximum number of entries to return.
            offset: Number of entries to skip.
            entity_type: Filter by entity type.
            action: Filter by action.

        Returns:
            List of History entries.
        """
        query = db.query(History).order_by(History.created_at.desc())

        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        if action:
            query = query.filter_by(action=action)

        query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()
