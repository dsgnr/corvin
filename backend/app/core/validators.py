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
