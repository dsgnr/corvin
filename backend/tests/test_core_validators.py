"""Tests for core validators module."""

import pytest

from app.core.exceptions import ValidationError
from app.core.validators import (
    validate_sponsorblock_behaviour,
    validate_sponsorblock_categories,
)


class TestValidateSponsorblockCategories:
    """Tests for validate_sponsorblock_categories function."""

    def test_accepts_empty_list(self):
        """Should accept empty list."""
        validate_sponsorblock_categories([])

    def test_accepts_valid_single_category(self):
        """Should accept valid single category."""
        validate_sponsorblock_categories(["sponsor"])

    def test_accepts_valid_multiple_categories(self):
        """Should accept valid multiple categories."""
        validate_sponsorblock_categories(["sponsor", "intro", "outro"])

    def test_rejects_invalid_category(self):
        """Should reject invalid category."""
        with pytest.raises(ValidationError) as exc_info:
            validate_sponsorblock_categories(["invalid_category"])

        assert "Invalid SponsorBlock categories" in str(exc_info.value.message)

    def test_rejects_mixed_valid_invalid(self):
        """Should reject when any category is invalid."""
        with pytest.raises(ValidationError):
            validate_sponsorblock_categories(["sponsor", "invalid", "intro"])

    def test_accepts_all_valid_categories(self):
        """Should accept all valid categories."""
        all_categories = [
            "sponsor",
            "intro",
            "outro",
            "selfpromo",
            "preview",
            "interaction",
            "music_offtopic",
            "filler",
        ]
        validate_sponsorblock_categories(all_categories)


class TestValidateSponsorblockBehaviour:
    """Tests for validate_sponsorblock_behaviour function."""

    def test_accepts_disabled(self):
        """Should accept 'disabled' behaviour."""
        validate_sponsorblock_behaviour("disabled")

    def test_accepts_delete(self):
        """Should accept 'delete' behaviour."""
        validate_sponsorblock_behaviour("delete")

    def test_accepts_mark_chapter(self):
        """Should accept 'mark_chapter' behaviour."""
        validate_sponsorblock_behaviour("mark_chapter")

    def test_accepts_empty_string(self):
        """Should accept empty string (falsy)."""
        validate_sponsorblock_behaviour("")

    def test_accepts_none(self):
        """Should accept None (falsy)."""
        validate_sponsorblock_behaviour(None)

    def test_rejects_invalid_behaviour(self):
        """Should reject invalid behaviour."""
        with pytest.raises(ValidationError) as exc_info:
            validate_sponsorblock_behaviour("invalid")

        assert "Invalid SponsorBlock behaviour" in str(exc_info.value.message)
