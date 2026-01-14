"""Tests for Settings model."""

from app.models.settings import Settings


class TestSettingsModel:
    """Test Settings model methods."""

    def test_get_returns_default_when_key_not_found(self, app):
        """Test get returns default value for missing key."""
        with app.app_context():
            result = Settings.get("nonexistent", "default_value")
            assert result == "default_value"

    def test_get_returns_empty_string_default(self, app):
        """Test get returns empty string when no default provided."""
        with app.app_context():
            result = Settings.get("nonexistent")
            assert result == ""

    def test_set_creates_new_setting(self, app):
        """Test set creates a new setting."""
        with app.app_context():
            Settings.set("test_key", "test_value")
            result = Settings.get("test_key")
            assert result == "test_value"

    def test_set_updates_existing_setting(self, app):
        """Test set updates an existing setting."""
        with app.app_context():
            Settings.set("test_key", "initial_value")
            Settings.set("test_key", "updated_value")
            result = Settings.get("test_key")
            assert result == "updated_value"

    def test_get_bool_returns_true_for_true_values(self, app):
        """Test get_bool returns True for various true representations."""
        with app.app_context():
            for value in ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]:
                Settings.set("bool_key", value)
                assert Settings.get_bool("bool_key") is True

    def test_get_bool_returns_false_for_false_values(self, app):
        """Test get_bool returns False for various false representations."""
        with app.app_context():
            for value in ["false", "False", "0", "no", "anything_else"]:
                Settings.set("bool_key", value)
                assert Settings.get_bool("bool_key") is False

    def test_get_bool_returns_default_when_key_not_found(self, app):
        """Test get_bool returns default for missing key."""
        with app.app_context():
            assert Settings.get_bool("nonexistent") is False
            assert Settings.get_bool("nonexistent", True) is True

    def test_set_bool_stores_true(self, app):
        """Test set_bool stores true correctly."""
        with app.app_context():
            Settings.set_bool("bool_key", True)
            assert Settings.get("bool_key") == "true"
            assert Settings.get_bool("bool_key") is True

    def test_set_bool_stores_false(self, app):
        """Test set_bool stores false correctly."""
        with app.app_context():
            Settings.set_bool("bool_key", False)
            assert Settings.get("bool_key") == "false"
            assert Settings.get_bool("bool_key") is False

    def test_multiple_settings(self, app):
        """Test multiple settings can coexist."""
        with app.app_context():
            Settings.set("key1", "value1")
            Settings.set("key2", "value2")
            Settings.set_bool("key3", True)

            assert Settings.get("key1") == "value1"
            assert Settings.get("key2") == "value2"
            assert Settings.get_bool("key3") is True
