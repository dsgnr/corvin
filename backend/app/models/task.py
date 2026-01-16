from datetime import datetime
from enum import Enum

from app.extensions import db
from app.models.video import Video
from app.models.video_list import VideoList


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


class Task(db.Model):
    """Background task persisted to database."""

    __tablename__ = "tasks"

    id: int = db.Column(db.Integer, primary_key=True)
    task_type: str = db.Column(db.String(20), nullable=False)
    entity_id: int = db.Column(db.Integer, nullable=False)
    status: str = db.Column(db.String(20), default=TaskStatus.PENDING.value)
    result: str | None = db.Column(db.Text, nullable=True)
    error: str | None = db.Column(db.Text, nullable=True)
    retry_count: int = db.Column(db.Integer, default=0)
    max_retries: int = db.Column(db.Integer, default=3)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    started_at: datetime | None = db.Column(db.DateTime, nullable=True)
    completed_at: datetime | None = db.Column(db.DateTime, nullable=True)

    logs = db.relationship(
        "TaskLog", back_populates="task", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index("ix_tasks_status_type", "status", "task_type"),
        db.Index("ix_tasks_pending_lookup", "task_type", "entity_id", "status"),
    )

    def add_log(
        self,
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
        db.session.add(log)
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
        """Get the name/title of the related entity."""
        if self.task_type == TaskType.SYNC.value:
            video_list = (
                db.session.query(VideoList.name).filter_by(id=self.entity_id).first()
            )
            return video_list[0] if video_list else None
        if self.task_type == TaskType.DOWNLOAD.value:
            video = db.session.query(Video.title).filter_by(id=self.entity_id).first()
            return video[0] if video else None
        return None

    @staticmethod
    def batch_get_entity_names(tasks: list["Task"]) -> dict[int, str]:
        """Batch fetch entity names for multiple tasks to avoid N+1 queries."""
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
                db.session.query(VideoList.id, VideoList.name)
                .filter(VideoList.id.in_(sync_entity_ids))
                .all()
            )
            list_names = {r[0]: r[1] for r in results}

        if download_entity_ids:
            results = (
                db.session.query(Video.id, Video.title)
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


class TaskLog(db.Model):
    """Log entry for a task attempt."""

    __tablename__ = "task_logs"

    id: int = db.Column(db.Integer, primary_key=True)
    task_id: int = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    attempt: int = db.Column(db.Integer, nullable=False)
    level: str = db.Column(db.String(10), default=TaskLogLevel.INFO.value)
    message: str = db.Column(db.Text, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship("Task", back_populates="logs")

    __table_args__ = (db.Index("ix_task_logs_task_id", "task_id"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "attempt": self.attempt,
            "level": self.level,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
