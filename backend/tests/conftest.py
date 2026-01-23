"""Pytest fixtures."""

import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import get_db
from app.models import Base, History, HistoryAction, Profile, Video, VideoList
from app.models.task import Task, TaskStatus, TaskType

# Modules that import SessionLocal/ReadSessionLocal directly and need patching
_SESSION_MODULES = [
    "app.extensions",
    "app.tasks",
    "app.task_queue",
    "app.metrics",
    "app.routes.lists",
    "app.routes.videos",
    "app.routes.history",
    "app.routes.tasks",
]


def _patch_session_factories(test_factory):
    """
    Patch SessionLocal and ReadSessionLocal in all modules that import them directly.

    This is necessary because Python caches imports - patching app.extensions.SessionLocal
    after modules have imported it doesn't affect their local reference.
    """
    for module_name in _SESSION_MODULES:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            if hasattr(module, "SessionLocal"):
                module.SessionLocal = test_factory
            if hasattr(module, "ReadSessionLocal"):
                module.ReadSessionLocal = test_factory


@pytest.fixture
def app():
    """Create application with test database."""
    # Store original factories for restoration
    import app.extensions as ext

    original_session = ext.SessionLocal
    original_read_session = ext.ReadSessionLocal

    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
    application = create_app(test_config)

    # Create test database engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Override FastAPI dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db

    # Patch SessionLocal in all modules that use it directly
    _patch_session_factories(TestingSessionLocal)

    # Store session factory for fixtures
    application.state.test_session_factory = TestingSessionLocal

    yield application

    # Restore original factories
    ext.SessionLocal = original_session
    ext.ReadSessionLocal = original_read_session
    _patch_session_factories(original_session)

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session(app):
    """Create a database session for tests."""
    session = app.state.test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_profile(app, db_session):
    """Create a sample profile."""
    profile = Profile(name="Test Profile")
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile.id


@pytest.fixture
def sample_list(app, db_session, sample_profile):
    """Create a sample video list."""
    video_list = VideoList(
        name="Test Channel",
        url="https://youtube.com/c/testchannel",
        profile_id=sample_profile,
        list_type="channel",
    )
    db_session.add(video_list)
    db_session.commit()
    db_session.refresh(video_list)
    return video_list.id


@pytest.fixture
def sample_video(app, db_session, sample_list):
    """Create a sample video."""
    video = Video(
        video_id="abc123",
        title="Test Video",
        url="https://youtube.com/watch?v=abc123",
        list_id=sample_list,
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video.id


@pytest.fixture
def sample_task(app, db_session, sample_list):
    """Create a sample task for testing."""
    task = Task(
        task_type=TaskType.SYNC.value,
        entity_id=sample_list,
        status=TaskStatus.PENDING.value,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task.id


@pytest.fixture
def sample_history(app, db_session):
    """Create sample history entries."""
    entries = [
        History(
            action=HistoryAction.PROFILE_CREATED.value,
            entity_type="profile",
            entity_id=1,
            details={"name": "Test Profile"},
        ),
        History(
            action=HistoryAction.LIST_CREATED.value,
            entity_type="list",
            entity_id=1,
            details={"name": "Test List"},
        ),
    ]
    db_session.add_all(entries)
    db_session.commit()
