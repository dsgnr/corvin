"""Tests for Settings model."""

from app.models.settings import Settings


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
