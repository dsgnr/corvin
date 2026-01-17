"""Tests for core helpers module."""

from unittest.mock import patch

from app.core.helpers import _get_pyproject_attr


class TestGetPyprojectAttr:
    """Tests for _get_pyproject_attr function."""

    def test_returns_default_on_exception(self):
        """Should return default when pyproject.toml cannot be read."""
        with patch("app.core.helpers._pyproject_data", None):
            with patch("builtins.open", side_effect=FileNotFoundError):
                result = _get_pyproject_attr("name", "default_name")
                assert result == "default_name"

    def test_returns_default_for_missing_key(self):
        """Should return default for missing key."""
        with patch("app.core.helpers._pyproject_data", {"project": {}}):
            result = _get_pyproject_attr("nonexistent", "fallback")
            assert result == "fallback"

    def test_returns_value_when_present(self):
        """Should return value when key exists."""
        with patch(
            "app.core.helpers._pyproject_data", {"project": {"name": "test-app"}}
        ):
            result = _get_pyproject_attr("name", "default")
            assert result == "test-app"

    def test_returns_unknown_as_default(self):
        """Should use 'unknown' as default when not specified."""
        with patch("app.core.helpers._pyproject_data", {"project": {}}):
            result = _get_pyproject_attr("missing")
            assert result == "unknown"
