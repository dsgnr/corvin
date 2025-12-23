"""Pytest fixtures."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Profile, Video, VideoList
from app.models.task import Task, TaskStatus, TaskType


@pytest.fixture
def app():
    """Create application."""
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
    application = create_app(test_config)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_profile(app):
    """Create a sample profile."""
    with app.app_context():
        profile = Profile(name="Test Profile")
        db.session.add(profile)
        db.session.commit()
        profile_id = profile.id
    return profile_id


@pytest.fixture
def sample_list(app, sample_profile):
    """Create a sample video list."""
    with app.app_context():
        video_list = VideoList(
            name="Test Channel",
            url="https://youtube.com/c/testchannel",
            profile_id=sample_profile,
            list_type="channel",
        )
        db.session.add(video_list)
        db.session.commit()
        list_id = video_list.id
    return list_id


@pytest.fixture
def sample_video(app, sample_list):
    """Create a sample video."""
    with app.app_context():
        video = Video(
            video_id="abc123",
            title="Test Video",
            url="https://youtube.com/watch?v=abc123",
            list_id=sample_list,
        )
        db.session.add(video)
        db.session.commit()
        video_id = video.id
    return video_id


@pytest.fixture
def sample_task(app, sample_list):
    """Create a sample task for testing."""
    with app.app_context():
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=sample_list,
            status=TaskStatus.PENDING.value,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    return task_id
