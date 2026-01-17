from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("errors")


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers for the application."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError):
        """Handle custom application errors."""
        logger.warning("AppError: %s", error.message)
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_dict(),
        )

    @app.exception_handler(404)
    async def handle_not_found(request: Request, exc):
        """Handle 404 errors."""
        return JSONResponse(
            status_code=404,
            content={"error": "Resource not found"},
        )

    @app.exception_handler(500)
    async def handle_internal_error(request: Request, exc):
        """Handle 500 errors."""
        logger.exception("Internal server error")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
