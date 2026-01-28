"""Validation functions."""

from app.core.constants import SPONSORBLOCK_BEHAVIOURS, SPONSORBLOCK_CATEGORIES
from app.core.exceptions import ValidationError


def validate_sponsorblock_categories(categories: list[str]) -> None:
    """
    Validate SponsorBlock category list.

    Args:
        categories: List of category names.

    Raises:
        ValidationError: If any category is invalid.
    """
    if not categories:
        return

    invalid_categories = [
        category for category in categories if category not in SPONSORBLOCK_CATEGORIES
    ]

    if invalid_categories:
        raise ValidationError(
            f"Invalid SponsorBlock categories: {invalid_categories}. "
            f"Valid categories: {list(SPONSORBLOCK_CATEGORIES.keys())}"
        )


def validate_sponsorblock_behaviour(behaviour: str) -> None:
    """
    Validate SponsorBlock behaviour value.

    Args:
        behaviour: The behaviour setting to validate.

    Raises:
        ValidationError: If the behaviour is invalid.
    """
    if behaviour and behaviour not in SPONSORBLOCK_BEHAVIOURS:
        raise ValidationError(
            f"Invalid SponsorBlock behaviour: {behaviour}. "
            f"Valid options: {SPONSORBLOCK_BEHAVIOURS}"
        )


def validate_extra_args(extra_args: dict | None) -> None:
    """
    Validate extra_args is a JSON serialisable dict.

    Args:
        extra_args: Dict to validate.

    Raises:
        ValidationError: If not a dict or not JSON serialisable.
    """
    import json

    if extra_args is None:
        return

    if not isinstance(extra_args, dict):
        raise ValidationError("extra_args must be a dict")

    try:
        json.dumps(extra_args)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"extra_args must be JSON serialisable: {e}") from e
