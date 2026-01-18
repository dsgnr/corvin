"""
Application exception classes.

Custom exceptions that map to HTTP status codes for consistent API error responses.
"""

from typing import Any


class AppError(Exception):
    """
    Base exception for application errors with HTTP status code support.

    All custom exceptions should inherit from this class to ensure
    consistent error handling and JSON response formatting.
    """

    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_dict(self) -> dict:
        """Convert the error to a dictionary for JSON responses."""
        return {
            "error": self.message,
            "details": self.details,
        }


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=404,
        )


class ConflictError(AppError):
    """Raised when an operation conflicts with existing data."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=409)


class ValidationError(AppError):
    """Raised when input data fails validation."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=400, details=details)
