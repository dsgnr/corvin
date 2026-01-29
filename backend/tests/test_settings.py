"""Tests for Settings model."""

from app.models.settings import (
    DEFAULT_DATA_RETENTION_DAYS,
    SETTING_DATA_RETENTION_DAYS,
    Settings,
)


class TestSettingsModel:
    """Test Settings model methods."""

    def test_get_returns_default_when_key_not_found(self, db_session):
        """Test get returns default value for missing key."""
        result = Settings.get(db_session, "nonexistent", "default_value")
        assert result == "default_value"

    def test_get_returns_empty_string_default(self, db_session):
        """Test get returns empty string when no default provided."""
        result = Settings.get(db_session, "nonexistent")
        assert result == ""

    def test_set_creates_new_setting(self, db_session):
        """Test set creates a new setting."""
        Settings.set(db_session, "test_key", "test_value")
        result = Settings.get(db_session, "test_key")
        assert result == "test_value"

    def test_set_updates_existing_setting(self, db_session):
        """Test set updates an existing setting."""
        Settings.set(db_session, "test_key", "initial_value")
        Settings.set(db_session, "test_key", "updated_value")
        result = Settings.get(db_session, "test_key")
        assert result == "updated_value"

    def test_get_bool_returns_true_for_true_values(self, db_session):
        """Test get_bool returns True for various true representations."""
        for value in ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]:
            Settings.set(db_session, "bool_key", value)
            assert Settings.get_bool(db_session, "bool_key") is True

    def test_get_bool_returns_false_for_false_values(self, db_session):
        """Test get_bool returns False for various false representations."""
        for value in ["false", "False", "0", "no", "anything_else"]:
            Settings.set(db_session, "bool_key", value)
            assert Settings.get_bool(db_session, "bool_key") is False

    def test_get_bool_returns_default_when_key_not_found(self, db_session):
        """Test get_bool returns default for missing key."""
        assert Settings.get_bool(db_session, "nonexistent") is False
        assert Settings.get_bool(db_session, "nonexistent", True) is True

    def test_set_bool_stores_true(self, db_session):
        """Test set_bool stores true correctly."""
        Settings.set_bool(db_session, "bool_key", True)
        assert Settings.get(db_session, "bool_key") == "true"
        assert Settings.get_bool(db_session, "bool_key") is True

    def test_set_bool_stores_false(self, db_session):
        """Test set_bool stores false correctly."""
        Settings.set_bool(db_session, "bool_key", False)
        assert Settings.get(db_session, "bool_key") == "false"
        assert Settings.get_bool(db_session, "bool_key") is False

    def test_get_int_returns_default_when_key_not_found(self, db_session):
        """Test get_int returns default value for missing key."""
        result = Settings.get_int(db_session, "nonexistent", 42)
        assert result == 42

    def test_get_int_returns_zero_default(self, db_session):
        """Test get_int returns 0 when no default provided."""
        result = Settings.get_int(db_session, "nonexistent")
        assert result == 0

    def test_get_int_returns_stored_value(self, db_session):
        """Test get_int returns stored integer value."""
        Settings.set(db_session, "int_key", "123")
        result = Settings.get_int(db_session, "int_key")
        assert result == 123

    def test_get_int_returns_default_for_invalid_value(self, db_session):
        """Test get_int returns default for non-integer values."""
        Settings.set(db_session, "int_key", "not_a_number")
        result = Settings.get_int(db_session, "int_key", 99)
        assert result == 99

    def test_set_int_stores_value(self, db_session):
        """Test set_int stores integer correctly."""
        Settings.set_int(db_session, "int_key", 456)
        assert Settings.get(db_session, "int_key") == "456"
        assert Settings.get_int(db_session, "int_key") == 456

    def test_set_int_updates_existing_value(self, db_session):
        """Test set_int updates existing integer value."""
        Settings.set_int(db_session, "int_key", 100)
        Settings.set_int(db_session, "int_key", 200)
        assert Settings.get_int(db_session, "int_key") == 200


class TestDataRetentionSettings:
    """Test data retention settings constants."""

    def test_default_retention_days(self):
        """Test default retention days constant."""
        assert DEFAULT_DATA_RETENTION_DAYS == 90

    def test_setting_key_defined(self):
        """Test setting key constant is defined."""
        assert SETTING_DATA_RETENTION_DAYS == "data_retention_days"


class TestSettingsAPI:
    """Test settings API endpoints."""

    def test_get_data_retention_default(self, client):
        """Test getting default data retention setting."""
        response = client.get("/api/settings/data-retention")
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 90

    def test_update_data_retention(self, client):
        """Test updating data retention setting."""
        response = client.put(
            "/api/settings/data-retention",
            json={"retention_days": 30},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 30

        # Verify it persisted
        response = client.get("/api/settings/data-retention")
        assert response.json()["retention_days"] == 30

    def test_update_data_retention_to_zero(self, client):
        """Test disabling data retention by setting to 0."""
        response = client.put(
            "/api/settings/data-retention",
            json={"retention_days": 0},
        )
        assert response.status_code == 200
        assert response.json()["retention_days"] == 0

    def test_update_data_retention_max_value(self, client):
        """Test setting maximum retention value."""
        response = client.put(
            "/api/settings/data-retention",
            json={"retention_days": 365},
        )
        assert response.status_code == 200
        assert response.json()["retention_days"] == 365

    def test_update_data_retention_invalid_negative(self, client):
        """Test rejection of negative retention value."""
        response = client.put(
            "/api/settings/data-retention",
            json={"retention_days": -1},
        )
        assert response.status_code == 400

    def test_update_data_retention_invalid_too_large(self, client):
        """Test rejection of retention value exceeding maximum."""
        response = client.put(
            "/api/settings/data-retention",
            json={"retention_days": 3651},
        )
        assert response.status_code == 400


class TestVacuumAPI:
    """Test vacuum API endpoint."""

    def test_vacuum_returns_success_for_sqlite(self, client):
        """Test vacuum endpoint returns success for SQLite."""
        response = client.post("/api/settings/vacuum")
        assert response.status_code == 200
        data = response.json()
        # In test environment, we use SQLite in-memory, so vacuum should work
        # but file size operations may not work as expected
        assert "success" in data
        assert "message" in data
