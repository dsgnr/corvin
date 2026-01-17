"""Tests for HistoryService."""

from app.models import HistoryAction
from app.services import HistoryService


class TestHistoryServiceLog:
    """Tests for HistoryService.log method."""

    def test_creates_history_entry(self, db_session):
        """Should create a history entry."""
        entry = HistoryService.log(
            db_session,
            HistoryAction.PROFILE_CREATED,
            "profile",
            entity_id=1,
            details={"name": "Test"},
        )

        assert entry.id is not None
        assert entry.action == "profile_created"
        assert entry.entity_type == "profile"
        assert entry.entity_id == 1

    def test_stores_details_as_json(self, db_session):
        """Should serialise details to JSON."""
        entry = HistoryService.log(
            db_session,
            HistoryAction.LIST_CREATED,
            "list",
            entity_id=1,
            details={"name": "My List", "url": "https://example.com"},
        )

        assert entry.details.get("name") == "My List"

    def test_handles_no_details(self, db_session):
        """Should handle missing details."""
        entry = HistoryService.log(
            db_session,
            HistoryAction.PROFILE_DELETED,
            "profile",
            entity_id=1,
        )

        assert isinstance(entry.details, dict)

    def test_handles_no_entity_id(self, db_session):
        """Should handle missing entity_id."""
        entry = HistoryService.log(
            db_session,
            HistoryAction.VIDEO_DISCOVERED,
            "video",
        )

        assert entry.entity_id is None


class TestHistoryServiceGetAll:
    """Tests for HistoryService.get_all method."""

    def test_returns_empty_list(self, db_session):
        """Should return empty list when no entries exist."""
        entries = HistoryService.get_all(db_session)

        assert entries == []

    def test_returns_entries(self, db_session):
        """Should return all entries."""
        HistoryService.log(db_session, HistoryAction.PROFILE_CREATED, "profile", 1)
        HistoryService.log(db_session, HistoryAction.LIST_CREATED, "list", 1)

        entries = HistoryService.get_all(db_session)

        assert len(entries) == 2

    def test_filters_by_entity_type(self, db_session):
        """Should filter by entity_type."""
        HistoryService.log(db_session, HistoryAction.PROFILE_CREATED, "profile", 1)
        HistoryService.log(db_session, HistoryAction.LIST_CREATED, "list", 1)

        entries = HistoryService.get_all(db_session, entity_type="profile")

        assert len(entries) == 1
        assert entries[0].entity_type == "profile"

    def test_filters_by_action(self, db_session):
        """Should filter by action."""
        HistoryService.log(db_session, HistoryAction.PROFILE_CREATED, "profile", 1)
        HistoryService.log(db_session, HistoryAction.PROFILE_UPDATED, "profile", 1)

        entries = HistoryService.get_all(db_session, action="profile_created")

        assert len(entries) == 1
        assert entries[0].action == "profile_created"

    def test_respects_limit(self, db_session):
        """Should respect limit parameter."""
        for i in range(5):
            HistoryService.log(db_session, HistoryAction.PROFILE_CREATED, "profile", i)

        entries = HistoryService.get_all(db_session, limit=2)

        assert len(entries) == 2

    def test_respects_offset(self, db_session):
        """Should respect offset parameter."""
        for i in range(5):
            HistoryService.log(db_session, HistoryAction.PROFILE_CREATED, "profile", i)

        entries = HistoryService.get_all(db_session, limit=10, offset=3)

        assert len(entries) == 2
