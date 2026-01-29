"""Tests for data retention and pruning functionality."""

from datetime import datetime, timedelta

from app.models import History, HistoryAction
from app.models.settings import SETTING_DATA_RETENTION_DAYS, Settings
from app.models.task import Task, TaskStatus, TaskType
from app.tasks import prune_old_data


class TestPruneOldData:
    """Tests for the prune_old_data function."""

    def test_prune_deletes_old_completed_tasks(self, app, db_session):
        """Test that old completed tasks are deleted."""
        old_date = datetime.utcnow() - timedelta(days=100)
        recent_date = datetime.utcnow() - timedelta(days=10)

        # Create old completed task
        old_task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.COMPLETED.value,
            created_at=old_date,
        )
        # Create recent completed task
        recent_task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=2,
            status=TaskStatus.COMPLETED.value,
            created_at=recent_date,
        )
        db_session.add_all([old_task, recent_task])
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 1
        assert result["retention_days"] == 90

        # Verify old task is gone, recent task remains
        remaining = db_session.query(Task).all()
        assert len(remaining) == 1
        assert remaining[0].entity_id == 2

    def test_prune_deletes_old_failed_tasks(self, app, db_session):
        """Test that old failed tasks are deleted."""
        old_date = datetime.utcnow() - timedelta(days=100)

        old_task = Task(
            task_type=TaskType.DOWNLOAD.value,
            entity_id=1,
            status=TaskStatus.FAILED.value,
            created_at=old_date,
        )
        db_session.add(old_task)
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 1
        assert db_session.query(Task).count() == 0

    def test_prune_deletes_old_cancelled_tasks(self, app, db_session):
        """Test that old cancelled tasks are deleted."""
        old_date = datetime.utcnow() - timedelta(days=100)

        old_task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.CANCELLED.value,
            created_at=old_date,
        )
        db_session.add(old_task)
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 1

    def test_prune_preserves_pending_tasks(self, app, db_session):
        """Test that pending tasks are never deleted regardless of age."""
        old_date = datetime.utcnow() - timedelta(days=100)

        pending_task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.PENDING.value,
            created_at=old_date,
        )
        db_session.add(pending_task)
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 0
        assert db_session.query(Task).count() == 1

    def test_prune_preserves_running_tasks(self, app, db_session):
        """Test that running tasks are never deleted regardless of age."""
        old_date = datetime.utcnow() - timedelta(days=100)

        running_task = Task(
            task_type=TaskType.DOWNLOAD.value,
            entity_id=1,
            status=TaskStatus.RUNNING.value,
            created_at=old_date,
        )
        db_session.add(running_task)
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 0
        assert db_session.query(Task).count() == 1

    def test_prune_deletes_old_history(self, app, db_session):
        """Test that old history entries are deleted."""
        old_date = datetime.utcnow() - timedelta(days=100)
        recent_date = datetime.utcnow() - timedelta(days=10)

        old_history = History(
            action=HistoryAction.LIST_SYNCED.value,
            entity_type="list",
            entity_id=1,
            created_at=old_date,
        )
        recent_history = History(
            action=HistoryAction.LIST_SYNCED.value,
            entity_type="list",
            entity_id=2,
            created_at=recent_date,
        )
        db_session.add_all([old_history, recent_history])
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_history"] == 1
        remaining = db_session.query(History).all()
        assert len(remaining) == 1
        assert remaining[0].entity_id == 2

    def test_prune_respects_custom_retention_days(self, app, db_session):
        """Test that custom retention setting is respected."""
        # Set retention to 30 days
        Settings.set_int(db_session, SETTING_DATA_RETENTION_DAYS, 30)

        # Create task that's 50 days old (should be deleted with 30-day retention)
        old_date = datetime.utcnow() - timedelta(days=50)
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.COMPLETED.value,
            created_at=old_date,
        )
        db_session.add(task)
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 1
        assert result["retention_days"] == 30

    def test_prune_disabled_when_retention_zero(self, app, db_session):
        """Test that pruning is disabled when retention is set to 0."""
        Settings.set_int(db_session, SETTING_DATA_RETENTION_DAYS, 0)

        old_date = datetime.utcnow() - timedelta(days=1000)
        task = Task(
            task_type=TaskType.SYNC.value,
            entity_id=1,
            status=TaskStatus.COMPLETED.value,
            created_at=old_date,
        )
        history = History(
            action=HistoryAction.LIST_SYNCED.value,
            entity_type="list",
            entity_id=1,
            created_at=old_date,
        )
        db_session.add_all([task, history])
        db_session.commit()

        result = prune_old_data()

        assert result["deleted_tasks"] == 0
        assert result["deleted_history"] == 0
        assert result["retention_days"] == 0
        assert db_session.query(Task).count() == 1
        assert db_session.query(History).count() == 1

    def test_prune_handles_empty_database(self, app, db_session):
        """Test that pruning works with no data."""
        result = prune_old_data()

        assert result["deleted_tasks"] == 0
        assert result["deleted_history"] == 0
        assert result["retention_days"] == 90
