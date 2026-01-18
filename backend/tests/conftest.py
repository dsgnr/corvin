"""Pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import get_db
from app.models import Base, History, HistoryAction, Profile, Video, VideoList
from app.models.task import Task, TaskStatus, TaskType


@pytest.fixture
def app():
    """Create application."""
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

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db

    # Also patch SessionLocal and ReadSessionLocal for helpers that use them directly
    import app.extensions
    import app.routes.history
    import app.routes.lists
    import app.routes.tasks
    import app.routes.videos
    import app.sse_stream

    app.extensions.SessionLocal = TestingSessionLocal
    app.extensions.ReadSessionLocal = TestingSessionLocal
    app.routes.lists.SessionLocal = TestingSessionLocal
    app.routes.lists.ReadSessionLocal = TestingSessionLocal
    app.routes.tasks.SessionLocal = TestingSessionLocal
    app.routes.tasks.ReadSessionLocal = TestingSessionLocal
    app.routes.videos.SessionLocal = TestingSessionLocal
    app.routes.videos.ReadSessionLocal = TestingSessionLocal
    app.routes.history.SessionLocal = TestingSessionLocal
    app.routes.history.ReadSessionLocal = TestingSessionLocal

    # Store session factory for fixtures
    application.state.test_session_factory = TestingSessionLocal

    yield application

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
