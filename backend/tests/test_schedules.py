"""Tests for download schedules functionality."""

from datetime import datetime, time
from unittest.mock import patch

import pytest

from app.models.download_schedule import DownloadSchedule


class TestScheduleCRUD:
    """Tests for schedule CRUD operations."""

    def test_create_schedule(self, client):
        """Create a new download schedule."""
        response = client.post(
            "/api/schedules",
            json={
                "name": "Night Downloads",
                "enabled": True,
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
                "start_time": "22:00",
                "end_time": "06:00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Night Downloads"
        assert data["enabled"] is True
        assert set(data["days_of_week"]) == {"mon", "tue", "wed", "thu", "fri"}
        assert data["start_time"] == "22:00"
        assert data["end_time"] == "06:00"

    def test_create_schedule_all_days(self, client):
        """Create a schedule for all days."""
        response = client.post(
            "/api/schedules",
            json={
                "name": "Always On",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["days_of_week"]) == 7

    def test_create_schedule_invalid_day(self, client):
        """Reject invalid day of week."""
        import pytest
        from fastapi.exceptions import RequestValidationError

        with pytest.raises((RequestValidationError, TypeError)):
            client.post(
                "/api/schedules",
                json={
                    "name": "Invalid",
                    "days_of_week": ["monday"],  # Should be "mon"
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
            )

    def test_create_schedule_invalid_time(self, client):
        """Reject invalid time format."""
        import pytest
        from fastapi.exceptions import RequestValidationError

        with pytest.raises((RequestValidationError, TypeError)):
            client.post(
                "/api/schedules",
                json={
                    "name": "Invalid Time",
                    "days_of_week": ["mon"],
                    "start_time": "25:00",  # Invalid hour
                    "end_time": "17:00",
                },
            )

    def test_list_schedules(self, client, db_session):
        """List all schedules."""
        # Create schedules
        schedules = [
            DownloadSchedule(
                name="Schedule A",
                days_of_week="mon,tue",
                start_time=time(9, 0),
                end_time=time(17, 0),
            ),
            DownloadSchedule(
                name="Schedule B",
                days_of_week="sat,sun",
                start_time=time(0, 0),
                end_time=time(23, 59),
            ),
        ]
        db_session.add_all(schedules)
        db_session.commit()

        response = client.get("/api/schedules")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {s["name"] for s in data}
        assert names == {"Schedule A", "Schedule B"}

    def test_get_schedule(self, client, db_session):
        """Get a specific schedule."""
        schedule = DownloadSchedule(
            name="Test Schedule",
            days_of_week="mon,wed,fri",
            start_time=time(10, 0),
            end_time=time(18, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        response = client.get(f"/api/schedules/{schedule.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Schedule"
        assert data["days_of_week"] == ["mon", "wed", "fri"]

    def test_get_schedule_not_found(self, client):
        """Return 404 for non-existent schedule."""
        response = client.get("/api/schedules/9999")

        assert response.status_code == 404

    def test_update_schedule(self, client, db_session):
        """Update an existing schedule."""
        schedule = DownloadSchedule(
            name="Original Name",
            days_of_week="mon",
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        response = client.put(
            f"/api/schedules/{schedule.id}",
            json={
                "name": "Updated Name",
                "days_of_week": ["mon", "tue", "wed"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert set(data["days_of_week"]) == {"mon", "tue", "wed"}
        # Unchanged fields should remain
        assert data["start_time"] == "09:00"

    def test_update_schedule_toggle_enabled(self, client, db_session):
        """Toggle schedule enabled status."""
        schedule = DownloadSchedule(
            name="Toggle Test",
            enabled=True,
            days_of_week="mon",
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        response = client.put(
            f"/api/schedules/{schedule.id}",
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_update_schedule_not_found(self, client):
        """Return 404 when updating non-existent schedule."""
        response = client.put(
            "/api/schedules/9999",
            json={"name": "New Name"},
        )

        assert response.status_code == 404

    def test_delete_schedule(self, client, db_session):
        """Delete a schedule."""
        schedule = DownloadSchedule(
            name="To Delete",
            days_of_week="mon",
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(schedule)
        db_session.commit()
        schedule_id = schedule.id

        response = client.delete(f"/api/schedules/{schedule_id}")

        assert response.status_code == 204

        # Verify deleted - need to expire the session first
        db_session.expire_all()
        assert db_session.get(DownloadSchedule, schedule_id) is None

    def test_delete_schedule_not_found(self, client):
        """Return 404 when deleting non-existent schedule."""
        response = client.delete("/api/schedules/9999")

        assert response.status_code == 404


class TestScheduleStatus:
    """Tests for schedule status endpoint."""

    def test_status_no_schedules(self, client):
        """Downloads allowed when no schedules exist."""
        response = client.get("/api/schedules/status")

        assert response.status_code == 200
        data = response.json()
        assert data["downloads_allowed"] is True
        assert data["active_schedules"] == 0

    def test_status_with_disabled_schedules(self, client, db_session):
        """Downloads allowed when all schedules are disabled."""
        schedule = DownloadSchedule(
            name="Disabled",
            enabled=False,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        db_session.add(schedule)
        db_session.commit()

        response = client.get("/api/schedules/status")

        assert response.status_code == 200
        data = response.json()
        assert data["downloads_allowed"] is True
        assert data["active_schedules"] == 0


class TestIsDownloadAllowed:
    """Tests for DownloadSchedule.is_download_allowed method."""

    def test_no_schedules_allows_download(self, db_session):
        """Allow downloads when no schedules exist."""
        result = DownloadSchedule.is_download_allowed(db_session)
        assert result is True

    def test_disabled_schedules_allows_download(self, db_session):
        """Allow downloads when all schedules are disabled."""
        schedule = DownloadSchedule(
            name="Disabled",
            enabled=False,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        db_session.add(schedule)
        db_session.commit()

        result = DownloadSchedule.is_download_allowed(db_session)
        assert result is True

    def test_within_schedule_allows_download(self, db_session):
        """Allow downloads when within scheduled time window."""
        # Create a schedule that covers all days, all times
        schedule = DownloadSchedule(
            name="Always On",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        db_session.add(schedule)
        db_session.commit()

        result = DownloadSchedule.is_download_allowed(db_session)
        assert result is True

    def test_outside_schedule_blocks_download(self, db_session):
        """Block downloads when outside scheduled time window."""
        # Create a schedule for a very narrow window that's unlikely to be now
        schedule = DownloadSchedule(
            name="Narrow Window",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(3, 0),
            end_time=time(3, 1),  # Only 1 minute window at 3am
        )
        db_session.add(schedule)
        db_session.commit()

        # This will almost certainly be outside the window
        now = datetime.now()
        if now.hour == 3 and now.minute == 0:
            pytest.skip("Test running during the narrow window")

        result = DownloadSchedule.is_download_allowed(db_session)
        assert result is False

    def test_overnight_schedule(self, db_session):
        """Test overnight schedule handling."""
        # Create an overnight schedule (22:00 - 06:00)
        schedule = DownloadSchedule(
            name="Night Schedule",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(22, 0),
            end_time=time(6, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        # The result depends on current time
        now = datetime.now()
        current_time = now.time()

        result = DownloadSchedule.is_download_allowed(db_session)

        # Should be True if between 22:00-23:59 or 00:00-06:00
        if current_time >= time(22, 0) or current_time <= time(6, 0):
            assert result is True
        else:
            assert result is False

    def test_multiple_schedules_any_match(self, db_session):
        """Allow downloads if any schedule matches."""
        # Create two schedules - one that covers all times
        schedule1 = DownloadSchedule(
            name="Narrow",
            enabled=True,
            days_of_week="mon",  # Only Monday
            start_time=time(3, 0),
            end_time=time(3, 1),
        )
        schedule2 = DownloadSchedule(
            name="Always",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        db_session.add_all([schedule1, schedule2])
        db_session.commit()

        result = DownloadSchedule.is_download_allowed(db_session)
        assert result is True  # schedule2 should always match


class TestScheduleModel:
    """Tests for DownloadSchedule model."""

    def test_to_dict(self, db_session):
        """Convert schedule to dictionary."""
        schedule = DownloadSchedule(
            name="Test",
            enabled=True,
            days_of_week="mon,wed,fri",
            start_time=time(9, 30),
            end_time=time(17, 45),
        )
        db_session.add(schedule)
        db_session.commit()

        result = schedule.to_dict()

        assert result["name"] == "Test"
        assert result["enabled"] is True
        assert result["days_of_week"] == ["mon", "wed", "fri"]
        assert result["start_time"] == "09:30"
        assert result["end_time"] == "17:45"
        assert "created_at" in result
        assert "updated_at" in result

    def test_default_enabled(self, db_session):
        """Default enabled to True."""
        schedule = DownloadSchedule(
            name="Default Test",
            days_of_week="mon",
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        assert schedule.enabled is True


class TestScheduleDownloadsIntegration:
    """Tests for schedule integration with download scheduling."""

    def test_schedule_downloads_respects_schedule(self, app, db_session, sample_list):
        """schedule_downloads should respect download schedules."""
        import app.tasks as tasks_module
        from app.models import Video, VideoList
        from app.tasks import schedule_downloads

        # Create a schedule that blocks current time (very narrow window)
        schedule = DownloadSchedule(
            name="Narrow Window",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(3, 0),
            end_time=time(3, 1),  # Only 1 minute at 3am
        )
        db_session.add(schedule)

        # Enable auto_download on the list
        video_list = db_session.query(VideoList).get(sample_list)
        video_list.auto_download = True

        # Create a pending video
        video = Video(
            video_id="schedule_test",
            title="Test Video",
            url="https://youtube.com/watch?v=schedule_test",
            list_id=sample_list,
            downloaded=False,
        )
        db_session.add(video)
        db_session.commit()

        # Skip if we happen to be in the narrow window
        now = datetime.now()
        if now.hour == 3 and now.minute == 0:
            pytest.skip("Test running during the narrow window")

        # Patch SessionLocal
        original_session_local = tasks_module.SessionLocal
        tasks_module.SessionLocal = app.state.test_session_factory

        try:
            result = schedule_downloads()

            # Should be blocked by schedule
            assert result["queued"] == 0
            assert result.get("reason") == "schedule"
        finally:
            tasks_module.SessionLocal = original_session_local

    def test_manual_downloads_bypass_schedule(self, app, db_session, sample_list):
        """Manual downloads (with video_ids) should bypass schedule."""
        import app.tasks as tasks_module
        from app.models import Video
        from app.tasks import schedule_downloads

        # Create a schedule that would block (but we're passing video_ids)
        schedule = DownloadSchedule(
            name="Blocking Schedule",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(3, 0),
            end_time=time(3, 1),  # Only allows 1 minute per day
        )
        db_session.add(schedule)

        # Create a pending video
        video = Video(
            video_id="manual_test",
            title="Manual Test Video",
            url="https://youtube.com/watch?v=manual_test",
            list_id=sample_list,
            downloaded=False,
        )
        db_session.add(video)
        db_session.commit()
        video_id = video.id

        # Patch SessionLocal
        original_session_local = tasks_module.SessionLocal
        tasks_module.SessionLocal = app.state.test_session_factory

        try:
            with patch("app.tasks.enqueue_tasks_bulk") as mock_enqueue:
                mock_enqueue.return_value = {"queued": 1, "skipped": 0, "tasks": []}

                # Pass specific video_ids - should bypass schedule
                schedule_downloads(video_ids=[video_id])

                # Should have called enqueue (schedule bypassed)
                mock_enqueue.assert_called_once()
        finally:
            tasks_module.SessionLocal = original_session_local


class TestTaskStatsIncludesSchedule:
    """Tests for schedule status in task stats."""

    def test_task_stats_includes_schedule_paused(self, client, db_session):
        """Task stats should include schedule_paused field."""
        # Create a blocking schedule
        schedule = DownloadSchedule(
            name="Blocking",
            enabled=True,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            start_time=time(0, 0),
            end_time=time(0, 1),
        )
        db_session.add(schedule)
        db_session.commit()

        response = client.get("/api/tasks/stats")

        assert response.status_code == 200
        data = response.json()
        assert "schedule_paused" in data

    def test_task_stats_schedule_not_paused_when_no_schedules(self, client):
        """schedule_paused should be False when no schedules."""
        response = client.get("/api/tasks/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["schedule_paused"] is False
