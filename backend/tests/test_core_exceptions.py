"""Tests for core exception classes."""

from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError


class TestAppError:
    """Tests for base AppError class."""

    def test_default_status_code(self):
        """Should default to 500 status code."""
        error = AppError("Something went wrong")

        assert error.status_code == 500
        assert error.message == "Something went wrong"

    def test_custom_status_code(self):
        """Should accept custom status code."""
        error = AppError("Custom error", status_code=418)

        assert error.status_code == 418

    def test_to_dict(self):
        """Should convert to dictionary."""
        error = AppError("Test error", details={"field": "value"})

        result = error.to_dict()

        assert result["error"] == "Test error"
        assert result["details"] == {"field": "value"}

    def test_to_dict_without_details(self):
        """Should handle missing details."""
        error = AppError("Test error")

        result = error.to_dict()

        assert result["details"] is None


class TestNotFoundError:
    """Tests for NotFoundError class."""

    def test_status_code(self):
        """Should have 404 status code."""
        error = NotFoundError("User", 123)

        assert error.status_code == 404

    def test_message_format(self):
        """Should format message with resource and identifier."""
        error = NotFoundError("Profile", 42)

        assert error.message == "Profile not found: 42"


class TestConflictError:
    """Tests for ConflictError class."""

    def test_status_code(self):
        """Should have 409 status code."""
        error = ConflictError("Resource already exists")

        assert error.status_code == 409

    def test_message(self):
        """Should preserve message."""
        error = ConflictError("Duplicate entry")

        assert error.message == "Duplicate entry"


class TestValidationError:
    """Tests for ValidationError class."""

    def test_status_code(self):
        """Should have 400 status code."""
        error = ValidationError("Invalid input")

        assert error.status_code == 400

    def test_with_details(self):
        """Should include validation details."""
        error = ValidationError("Invalid fields", details=["name", "email"])

        assert error.message == "Invalid fields"
        assert error.details == ["name", "email"]
