"""SQLAlchemy models."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Models must be imported after Base is defined so they can inherit from it
from app.models.download_schedule import DownloadSchedule  # noqa: E402
from app.models.history import History, HistoryAction  # noqa: E402
from app.models.profile import Profile  # noqa: E402
from app.models.settings import Settings  # noqa: E402
from app.models.task import Task, TaskStatus, TaskType  # noqa: E402
from app.models.video import Video  # noqa: E402
from app.models.video_list import VideoList  # noqa: E402

__all__ = [
    "Base",
    "DownloadSchedule",
    "Profile",
    "VideoList",
    "Video",
    "History",
    "HistoryAction",
    "Task",
    "TaskStatus",
    "TaskType",
    "Settings",
]
