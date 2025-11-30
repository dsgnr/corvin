from typing import Any


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "details": self.details,
        }


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=404,
        )


class ConflictError(AppError):
    """Resource conflict (duplicate, already exists, etc)."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=409)


class ValidationError(AppError):
    """Invalid input data."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message=message, status_code=400, details=details)
