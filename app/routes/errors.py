from flask import Blueprint, jsonify

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("errors")

bp = Blueprint("errors", __name__)


@bp.app_errorhandler(AppError)
def handle_app_error(error: AppError):
    """Handle custom application errors."""
    logger.warning("AppError: %s", error.message)
    return jsonify(error.to_dict()), error.status_code


@bp.app_errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Resource not found"}), 404


@bp.app_errorhandler(500)
def handle_internal_error(error):
    """Handle 500 errors."""
    logger.exception("Internal server error")
    return jsonify({"error": "Internal server error"}), 500
