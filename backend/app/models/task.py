"""
Task model for background job tracking.

Tasks represent sync and download operations that are processed by the
TaskWorker. Each task tracks its status, retry count, and execution logs.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    desc,
)
from sqlalchemy.orm import relationship

from app.models import Base


class TaskStatus(str, Enum):
    """States for a task."""

    PENDING = "pending"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Types of background tasks."""

    SYNC = "sync"
    DOWNLOAD = "download"


class TaskLogLevel(str, Enum):
    """Log levels for task log entries."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Task(Base):
    """
    Tasks are created when sync or download operations are requested
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    task_type = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    status = Column(String(20), default=TaskStatus.PENDING.value)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    logs = relationship(
        "TaskLog", back_populates="task", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_status_type", "status", "task_type"),
        Index("ix_tasks_pending_lookup", "task_type", "entity_id", "status"),
        Index(
            "ix_tasks_entity_type_created", "task_type", "entity_id", desc("created_at")
        ),
        Index("ix_tasks_entity_status", "entity_id", "status"),
    )

    def add_log(
        self,
        db,
        message: str,
        level: str = TaskLogLevel.INFO.value,
        attempt: int | None = None,
    ) -> "TaskLog":
        """
        Add a log entry to this task.

        Args:
            db: Database session.
            message: Log message.
            level: Log level.
            attempt: Attempt number, defaults to current retry_count + 1.

        Returns:
            The created TaskLog instance.
        """
        log = TaskLog(
            task_id=self.id,
            attempt=attempt if attempt is not None else self.retry_count + 1,
            level=level,
            message=message,
        )
        db.add(log)
        return log

    def to_dict(
        self, include_logs: bool = False, entity_name: str | None = None
    ) -> dict:
        """
        Convert to dictionary for JSON serialisation.

        Args:
            include_logs: Whether to include log entries.
            entity_name: Pre-fetched entity name to avoid extra queries.

        Returns:
            Dictionary representation of the task.
        """
        data = {
            "id": self.id,
            "task_type": self.task_type,
            "entity_id": self.entity_id,
            "entity_name": entity_name
            if entity_name is not None
            else self._get_entity_name(),
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }
        if include_logs:
            data["logs"] = [
                log.to_dict() for log in self.logs.order_by(TaskLog.created_at.asc())
            ]
        return data

    def _get_entity_name(self) -> str | None:
        """
        Get the list name/video title of the related entity.
        """
        from sqlalchemy.orm import Session

        from app.models.video import Video
        from app.models.video_list import VideoList

        session = Session.object_session(self)
        if session:
            if self.task_type == TaskType.SYNC.value:
                video_list = (
                    session.query(VideoList.name).filter_by(id=self.entity_id).first()
                )
                return video_list[0] if video_list else None
            if self.task_type == TaskType.DOWNLOAD.value:
                video = session.query(Video.title).filter_by(id=self.entity_id).first()
                return video[0] if video else None
            return None

        from app.extensions import SessionLocal

        with SessionLocal() as db:
            if self.task_type == TaskType.SYNC.value:
                video_list = (
                    db.query(VideoList.name).filter_by(id=self.entity_id).first()
                )
                return video_list[0] if video_list else None
            if self.task_type == TaskType.DOWNLOAD.value:
                video = db.query(Video.title).filter_by(id=self.entity_id).first()
                return video[0] if video else None
        return None

    @staticmethod
    def batch_get_entity_names(db, tasks: list["Task"]) -> dict[int, str]:
        """
        Batch fetch entity names for multiple tasks.

        Args:
            db: Database session.
            tasks: List of Task instances.

        Returns:
            Dictionary mapping task_id to entity_name.
        """
        from app.models.video import Video
        from app.models.video_list import VideoList

        if not tasks:
            return {}

        sync_entity_ids = [
            t.entity_id for t in tasks if t.task_type == TaskType.SYNC.value
        ]
        download_entity_ids = [
            t.entity_id for t in tasks if t.task_type == TaskType.DOWNLOAD.value
        ]

        list_names = {}
        video_titles = {}

        if sync_entity_ids:
            results = (
                db.query(VideoList.id, VideoList.name)
                .filter(VideoList.id.in_(sync_entity_ids))
                .all()
            )
            list_names = {r[0]: r[1] for r in results}

        if download_entity_ids:
            results = (
                db.query(Video.id, Video.title)
                .filter(Video.id.in_(download_entity_ids))
                .all()
            )
            video_titles = {r[0]: r[1] for r in results}

        result = {}
        for task in tasks:
            if task.task_type == TaskType.SYNC.value:
                result[task.id] = list_names.get(task.entity_id)
            elif task.task_type == TaskType.DOWNLOAD.value:
                result[task.id] = video_titles.get(task.entity_id)
            else:
                result[task.id] = None

        return result

    @staticmethod
    def row_to_dict(row) -> dict:
        """
        Convert a query result row (from JOIN query) to dictionary.

        This is for rows returned from queries that select specific columns
        with entity_name from JOINs, not for Task model instances.

        Args:
            row: A query result row with named attributes.

        Returns:
            Dictionary representation of the task.
        """
        return {
            "id": row.id,
            "task_type": row.task_type,
            "entity_id": row.entity_id,
            "entity_name": row.entity_name,
            "status": row.status,
            "result": row.result,
            "error": row.error,
            "retry_count": row.retry_count,
            "max_retries": row.max_retries,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }


class TaskLog(Base):
    """Log entry for a task attempt."""

    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    attempt = Column(Integer, nullable=False)
    level = Column(String(10), default=TaskLogLevel.INFO.value)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="logs")

    __table_args__ = (Index("ix_task_logs_task_id", "task_id"),)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialisation."""
        return {
            "id": self.id,
            "attempt": self.attempt,
            "level": self.level,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
