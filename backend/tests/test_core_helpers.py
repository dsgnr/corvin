"""Tests for core helpers module."""

from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.core.helpers import _get_pyproject_attr, parse_from_date


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


class TestParseFromDate:
    """Tests for parse_from_date function."""

    def test_returns_none_for_none(self):
        """Should return None for None input."""
        assert parse_from_date(None) is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        assert parse_from_date("") is None

    def test_parses_yyyymmdd_format(self):
        """Should parse YYYYMMDD format."""
        result = parse_from_date("20240115")
        assert result == "20240115"

    def test_parses_date_with_dashes(self):
        """Should parse date with dashes and normalise."""
        result = parse_from_date("2024-01-15")
        assert result == "20240115"

    def test_rejects_invalid_format(self):
        """Should reject invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            parse_from_date("invalid")
        assert "Invalid from_date format" in str(exc_info.value.message)

    def test_rejects_too_short(self):
        """Should reject date that's too short."""
        with pytest.raises(ValidationError):
            parse_from_date("2024")

    def test_rejects_too_long(self):
        """Should reject date that's too long."""
        with pytest.raises(ValidationError):
            parse_from_date("202401150000")

    def test_rejects_invalid_date(self):
        """Should reject invalid date values."""
        with pytest.raises(ValidationError) as exc_info:
            parse_from_date("20241301")  # Invalid month
        assert "not a valid date" in str(exc_info.value.message)

    def test_rejects_non_numeric(self):
        """Should reject non-numeric characters."""
        with pytest.raises(ValidationError):
            parse_from_date("2024abcd")
