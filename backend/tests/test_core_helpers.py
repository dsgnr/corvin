"""Tests for core helpers module."""

import re
from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.core.helpers import (
    _get_pyproject_attr,
    calculate_total_pages,
    check_blacklist,
    compile_blacklist_pattern,
    parse_from_date,
)


class TestCalculateTotalPages:
    """Tests for calculate_total_pages function."""

    def test_returns_one_for_zero_items(self):
        """Should return 1 when there are no items."""
        assert calculate_total_pages(0, 10) == 1

    def test_returns_one_for_items_less_than_page_size(self):
        """Should return 1 when items fit on one page."""
        assert calculate_total_pages(5, 10) == 1

    def test_returns_one_for_items_equal_to_page_size(self):
        """Should return 1 when items exactly fill one page."""
        assert calculate_total_pages(10, 10) == 1

    def test_returns_two_for_items_exceeding_page_size(self):
        """Should return 2 when items exceed one page."""
        assert calculate_total_pages(11, 10) == 2

    def test_handles_exact_multiple(self):
        """Should handle exact multiples of page size."""
        assert calculate_total_pages(30, 10) == 3

    def test_handles_non_exact_multiple(self):
        """Should round up for non-exact multiples."""
        assert calculate_total_pages(25, 10) == 3

    def test_handles_large_numbers(self):
        """Should handle large numbers correctly."""
        assert calculate_total_pages(1000000, 100) == 10000


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


class TestCompileBlacklistPattern:
    """Tests for compile_blacklist_pattern function."""

    def test_returns_none_for_none_input(self):
        """Should return None when regex is None."""
        assert compile_blacklist_pattern(None) is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        assert compile_blacklist_pattern("") is None

    def test_returns_none_for_whitespace_only(self):
        """Should return None for whitespace-only string."""
        assert compile_blacklist_pattern("   ") is None

    def test_compiles_valid_pattern(self):
        """Should compile a valid regex pattern."""
        pattern = compile_blacklist_pattern("test.*video")
        assert pattern is not None
        assert pattern.search("test my video")
        assert not pattern.search("other content")

    def test_pattern_is_case_insensitive(self):
        """Should compile pattern as case-insensitive."""
        pattern = compile_blacklist_pattern("TEST")
        assert pattern is not None
        assert pattern.search("test")
        assert pattern.search("TEST")
        assert pattern.search("TeSt")

    def test_returns_none_for_invalid_regex(self):
        """Should return None for invalid regex."""
        pattern = compile_blacklist_pattern("[invalid")
        assert pattern is None

    def test_no_warning_without_logger(self):
        """Should not raise when logger is None and regex is invalid."""
        # Should not raise
        result = compile_blacklist_pattern("[invalid")
        assert result is None


class TestCheckBlacklist:
    """Tests for check_blacklist function."""

    def test_not_blacklisted_when_no_constraints(self):
        """Should not blacklist when no constraints are set."""
        is_blacklisted, reason = check_blacklist("Any Title", 100, None, None, None)
        assert is_blacklisted is False
        assert reason is None

    def test_blacklisted_by_title_pattern(self):
        """Should blacklist when title matches pattern."""
        pattern = re.compile("blocked", re.IGNORECASE)
        is_blacklisted, reason = check_blacklist(
            "This is blocked content", 100, pattern, None, None
        )
        assert is_blacklisted is True
        assert reason is not None
        assert "Title matches blacklist pattern" in reason

    def test_not_blacklisted_when_title_doesnt_match(self):
        """Should not blacklist when title doesn't match pattern."""
        pattern = re.compile("blocked", re.IGNORECASE)
        is_blacklisted, reason = check_blacklist(
            "Normal video title", 100, pattern, None, None
        )
        assert is_blacklisted is False
        assert reason is None

    def test_blacklisted_by_min_duration(self):
        """Should blacklist when duration is below minimum."""
        is_blacklisted, reason = check_blacklist("Title", 30, None, 60, None)
        assert is_blacklisted is True
        assert reason is not None
        assert "below minimum" in reason
        assert "30s" in reason
        assert "60s" in reason

    def test_blacklisted_by_max_duration(self):
        """Should blacklist when duration exceeds maximum."""
        is_blacklisted, reason = check_blacklist("Title", 120, None, None, 60)
        assert is_blacklisted is True
        assert reason is not None
        assert "exceeds maximum" in reason
        assert "120s" in reason
        assert "60s" in reason

    def test_not_blacklisted_when_duration_in_range(self):
        """Should not blacklist when duration is within range."""
        is_blacklisted, reason = check_blacklist("Title", 90, None, 60, 120)
        assert is_blacklisted is False
        assert reason is None

    def test_duration_at_exact_minimum(self):
        """Should not blacklist when duration equals minimum."""
        is_blacklisted, reason = check_blacklist("Title", 60, None, 60, None)
        assert is_blacklisted is False
        assert reason is None

    def test_duration_at_exact_maximum(self):
        """Should not blacklist when duration equals maximum."""
        is_blacklisted, reason = check_blacklist("Title", 120, None, None, 120)
        assert is_blacklisted is False
        assert reason is None

    def test_multiple_reasons_combined(self):
        """Should combine multiple blacklist reasons."""
        pattern = re.compile("blocked", re.IGNORECASE)
        is_blacklisted, reason = check_blacklist("Blocked video", 30, pattern, 60, 120)
        assert is_blacklisted is True
        assert reason is not None
        assert "Title matches blacklist pattern" in reason
        assert "below minimum" in reason
        assert "; " in reason  # Reasons are semicolon-separated

    def test_none_duration_skips_duration_checks(self):
        """Should skip duration checks when duration is None."""
        is_blacklisted, reason = check_blacklist("Title", None, None, 60, 120)
        assert is_blacklisted is False
        assert reason is None

    def test_none_duration_with_title_match(self):
        """Should still check title when duration is None."""
        pattern = re.compile("blocked", re.IGNORECASE)
        is_blacklisted, reason = check_blacklist(
            "Blocked video", None, pattern, 60, 120
        )
        assert is_blacklisted is True
        assert reason is not None
        assert "Title matches blacklist pattern" in reason
        assert "duration" not in reason.lower()
