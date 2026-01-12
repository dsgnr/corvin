"""Tests for HistoryService."""

from app.models import HistoryAction
from app.services import HistoryService


class TestHistoryServiceLog:
    """Tests for HistoryService.log method."""

    def test_creates_history_entry(self, app):
        """Should create a history entry."""
        with app.app_context():
            entry = HistoryService.log(
                HistoryAction.PROFILE_CREATED,
                "profile",
                entity_id=1,
                details={"name": "Test"},
            )

            assert entry.id is not None
            assert entry.action == "profile_created"
            assert entry.entity_type == "profile"
            assert entry.entity_id == 1

    def test_stores_details_as_json(self, app):
        """Should serialise details to JSON."""
        with app.app_context():
            entry = HistoryService.log(
                HistoryAction.LIST_CREATED,
                "list",
                entity_id=1,
                details={"name": "My List", "url": "https://example.com"},
            )

            assert entry.details.get("name") == "My List"

    def test_handles_no_details(self, app):
        """Should handle missing details."""
        with app.app_context():
            entry = HistoryService.log(
                HistoryAction.PROFILE_DELETED,
                "profile",
                entity_id=1,
            )

            assert isinstance(entry.details, dict)

    def test_handles_no_entity_id(self, app):
        """Should handle missing entity_id."""
        with app.app_context():
            entry = HistoryService.log(
                HistoryAction.VIDEO_DISCOVERED,
                "video",
            )

            assert entry.entity_id is None


class TestHistoryServiceGetAll:
    """Tests for HistoryService.get_all method."""

    def test_returns_empty_list(self, app):
        """Should return empty list when no entries exist."""
        with app.app_context():
            entries = HistoryService.get_all()

            assert entries == []

    def test_returns_entries(self, app):
        """Should return all entries."""
        with app.app_context():
            HistoryService.log(HistoryAction.PROFILE_CREATED, "profile", 1)
            HistoryService.log(HistoryAction.LIST_CREATED, "list", 1)

            entries = HistoryService.get_all()

            assert len(entries) == 2

    def test_filters_by_entity_type(self, app):
        """Should filter by entity_type."""
        with app.app_context():
            HistoryService.log(HistoryAction.PROFILE_CREATED, "profile", 1)
            HistoryService.log(HistoryAction.LIST_CREATED, "list", 1)

            entries = HistoryService.get_all(entity_type="profile")

            assert len(entries) == 1
            assert entries[0].entity_type == "profile"

    def test_filters_by_action(self, app):
        """Should filter by action."""
        with app.app_context():
            HistoryService.log(HistoryAction.PROFILE_CREATED, "profile", 1)
            HistoryService.log(HistoryAction.PROFILE_UPDATED, "profile", 1)

            entries = HistoryService.get_all(action="profile_created")

            assert len(entries) == 1
            assert entries[0].action == "profile_created"

    def test_respects_limit(self, app):
        """Should respect limit parameter."""
        with app.app_context():
            for i in range(5):
                HistoryService.log(HistoryAction.PROFILE_CREATED, "profile", i)

            entries = HistoryService.get_all(limit=2)

            assert len(entries) == 2

    def test_respects_offset(self, app):
        """Should respect offset parameter."""
        with app.app_context():
            for i in range(5):
                HistoryService.log(HistoryAction.PROFILE_CREATED, "profile", i)

            entries = HistoryService.get_all(limit=10, offset=3)

            assert len(entries) == 2
