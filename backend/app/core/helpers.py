"""Generic helper functions."""

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
