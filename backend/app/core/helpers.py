"""Generic helper functions."""

import re
import tomllib
from datetime import datetime
from pathlib import Path

from app.core.exceptions import ValidationError

_pyproject_data: dict | None = None


def _get_pyproject() -> dict:
    """Load and cache pyproject.toml data."""
    global _pyproject_data
    if _pyproject_data is None:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            _pyproject_data = tomllib.load(f)
    return _pyproject_data


def _get_pyproject_attr(key: str, default: str = "unknown") -> str:
    """
    Get an attribute from pyproject.toml [project] section.

    Args:
        key: The attribute name to retrieve.
        default: Default value if attribute not found.

    Returns:
        The attribute value or default.
    """
    try:
        return _get_pyproject()["project"].get(key, default)
    except Exception:
        return default


def calculate_total_pages(total: int, page_size: int) -> int:
    """
    Calculate the total number of pages for pagination.

    Args:
        total: Total number of items.
        page_size: Number of items per page.

    Returns:
        Total number of pages (minimum 1).
    """
    return max(1, (total + page_size - 1) // page_size)


def compile_blacklist_pattern(regex: str | None) -> re.Pattern | None:
    """
    Compile a blacklist regex pattern.

    Args:
        regex: The regex pattern string, or None.

    Returns:
        Compiled regex pattern, or None if regex is empty/invalid.
    """
    if not regex or not regex.strip():
        return None

    try:
        return re.compile(regex, re.IGNORECASE)
    except re.error:
        return None


def check_blacklist(
    title: str,
    duration: int | None,
    pattern: re.Pattern | None,
    min_duration: int | None,
    max_duration: int | None,
) -> tuple[bool, str | None]:
    """
    Check if a video should be blacklisted based on title and duration.

    Args:
        title: The video title to check.
        duration: The video duration in seconds, or None.
        pattern: Compiled regex pattern for title matching, or None.
        min_duration: Minimum allowed duration in seconds, or None.
        max_duration: Maximum allowed duration in seconds, or None.

    Returns:
        Tuple of (is_blacklisted, reason_string).
        reason_string is None if not blacklisted, otherwise contains
        semicolon-separated reasons.
    """
    reasons = []

    # Check title against pattern
    if pattern and pattern.search(title):
        reasons.append("Title matches blacklist pattern")

    # Check duration constraints
    if duration is not None:
        if min_duration is not None and duration < min_duration:
            reasons.append(f"Duration ({duration}s) is below minimum ({min_duration}s)")
        if max_duration is not None and duration > max_duration:
            reasons.append(f"Duration ({duration}s) exceeds maximum ({max_duration}s)")

    is_blacklisted = len(reasons) > 0
    reason_string = "; ".join(reasons) if reasons else None

    return is_blacklisted, reason_string


def parse_from_date(date_str: str | None) -> str | None:
    """
    Validate and normalise a date string to YYYYMMDD format.

    Args:
        date_str: Date string in YYYYMMDD or YYYY-MM-DD format.

    Returns:
        Normalised date string in YYYYMMDD format, or None if input is None.

    Raises:
        ValidationError: If the date format is invalid.
    """
    if not date_str:
        return None

    normalised = date_str.replace("-", "")
    if len(normalised) != 8 or not normalised.isdigit():
        raise ValidationError("Invalid from_date format (use YYYYMMDD)")

    try:
        datetime.strptime(normalised, "%Y%m%d")
    except ValueError as exc:
        raise ValidationError("Invalid from_date (not a valid date)") from exc

    return normalised
