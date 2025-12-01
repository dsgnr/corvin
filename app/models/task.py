from datetime import datetime
from enum import Enum

from app.extensions import db


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    SYNC = "sync"
    DOWNLOAD = "download"


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

    __table_args__ = (db.Index("ix_tasks_status_type", "status", "task_type"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
