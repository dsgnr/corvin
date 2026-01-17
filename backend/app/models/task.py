from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models import Base


class TaskStatus(str, Enum):
    PENDING = "pending"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    SYNC = "sync"
    DOWNLOAD = "download"


class TaskLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Task(Base):
    """Background task persisted to database."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    task_type = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    status = Column(String(20), default=TaskStatus.PENDING.value)
    result = Column(Text, nullable=True)
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
        Index("ix_tasks_status_type", "status", "task_type"),
        Index("ix_tasks_pending_lookup", "task_type", "entity_id", "status"),
    )

    def add_log(
        self,
        db,
        message: str,
        level: str = TaskLogLevel.INFO.value,
        attempt: int | None = None,
    ) -> "TaskLog":
        """Add a log entry to this task."""
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
        """Get the name/title of the related entity.

        Note: This creates a new session, so prefer using batch_get_entity_names()
        or passing entity_name directly to to_dict() when possible.
        """
        from sqlalchemy.orm import Session

        from app.models.video import Video
        from app.models.video_list import VideoList

        # Try to use the object's existing session first
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

        # Fallback to new session if object is detached
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
        """Batch fetch entity names for multiple tasks to avoid N+1 queries."""
        from app.models.video import Video
        from app.models.video_list import VideoList

        if not tasks:
            return {}

        # Group tasks by type
        sync_entity_ids = [
            t.entity_id for t in tasks if t.task_type == TaskType.SYNC.value
        ]
        download_entity_ids = [
            t.entity_id for t in tasks if t.task_type == TaskType.DOWNLOAD.value
        ]

        # Batch fetch names
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

        # Build result mapping task_id -> entity_name
        result = {}
        for task in tasks:
            if task.task_type == TaskType.SYNC.value:
                result[task.id] = list_names.get(task.entity_id)
            elif task.task_type == TaskType.DOWNLOAD.value:
                result[task.id] = video_titles.get(task.entity_id)
            else:
                result[task.id] = None

        return result


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
        return {
            "id": self.id,
            "attempt": self.attempt,
            "level": self.level,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
