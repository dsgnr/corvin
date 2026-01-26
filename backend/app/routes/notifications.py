"""
Notification routes.

Provides API endpoints for managing notification integrations
like Plex, Jellyfin, webhooks, etc.

Sensitive fields can be provided via environment variables as an alternative
to storing in the database. Environment variable names follow the pattern:
    NOTIFICATION_{NOTIFIER_ID}_{FIELD_NAME}

Example:
    NOTIFICATION_PLEX_TOKEN=your-plex-token
    NOTIFICATION_JELLYFIN_API_KEY=your-api-key
    NOTIFICATION_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
"""

import json
import os

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.extensions import get_db, get_read_db
from app.models import Settings
from app.schemas.notifications import NotifierConfigUpdate, NotifierTestRequest
from app.services.notifications import NotifierRegistry

logger = get_logger("routes.notifications")
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _get_env_var_name(notifier_id: str, field_name: str) -> str:
    """Get the environment variable name for a notifier field."""
    return f"NOTIFICATION_{notifier_id.upper()}_{field_name.upper()}"


def _get_config_with_env(config: dict, notifier_id: str, schema: dict) -> dict:
    """
    Merge config with environment variables.

    Environment variables take precedence over database values for sensitive fields.
    """
    merged = config.copy()

    for field_name, _field_schema in schema.items():
        env_name = _get_env_var_name(notifier_id, field_name)
        env_value = os.environ.get(env_name)
        if env_value:
            merged[field_name] = env_value

    return merged


def _is_field_from_env(notifier_id: str, field_name: str) -> bool:
    """Check if a field value is provided via environment variable."""
    env_name = _get_env_var_name(notifier_id, field_name)
    return bool(os.environ.get(env_name))


@router.get("")
def list_notifiers(db: Session = Depends(get_read_db)):
    """
    List all available notification methods with their current configuration.

    Returns a list of notifiers with their schemas and current enabled/config state.
    """
    notifiers = NotifierRegistry.all()

    result = []
    for notifier in notifiers:
        notifier_id = notifier["id"]

        enabled = Settings.get_bool(db, f"notification_{notifier_id}_enabled", False)
        config_json = Settings.get(db, f"notification_{notifier_id}_config", "{}")

        try:
            config = json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            config = {}

        # Merge with environment variables
        config = _get_config_with_env(config, notifier_id, notifier["config_schema"])

        # Get event settings
        events = {}
        for event in notifier.get("supported_events", []):
            event_id = event["id"]
            default = event.get("default", False)
            events[event_id] = Settings.get_bool(
                db, f"notification_{notifier_id}_event_{event_id}", default
            )

        # Mask sensitive fields in response
        masked_config = _mask_sensitive_fields(
            config, notifier["config_schema"], notifier_id
        )

        result.append(
            {
                "id": notifier_id,
                "name": notifier["name"],
                "enabled": enabled,
                "config": masked_config,
                "config_schema": notifier["config_schema"],
                "supported_events": notifier.get("supported_events", []),
                "events": events,
            }
        )

    return result


@router.get("/{notifier_id}")
def get_notifier(notifier_id: str, db: Session = Depends(get_read_db)):
    """Get a specific notifier's configuration."""
    notifier_class = NotifierRegistry.get(notifier_id)

    if not notifier_class:
        raise NotFoundError("Notifier", notifier_id)

    enabled = Settings.get_bool(db, f"notification_{notifier_id}_enabled", False)
    config_json = Settings.get(db, f"notification_{notifier_id}_config", "{}")

    try:
        config = json.loads(config_json) if config_json else {}
    except json.JSONDecodeError:
        config = {}

    schema = notifier_class.get_config_schema()

    # Merge with environment variables
    config = _get_config_with_env(config, notifier_id, schema)

    supported_events = notifier_class.get_supported_events()
    masked_config = _mask_sensitive_fields(config, schema, notifier_id)

    # Get event settings
    events = {}
    for event in supported_events:
        event_id = event["id"]
        default = event.get("default", False)
        events[event_id] = Settings.get_bool(
            db, f"notification_{notifier_id}_event_{event_id}", default
        )

    return {
        "id": notifier_id,
        "name": notifier_class.name,
        "enabled": enabled,
        "config": masked_config,
        "config_schema": schema,
        "supported_events": supported_events,
        "events": events,
    }


@router.put("/{notifier_id}", status_code=status.HTTP_200_OK)
def update_notifier(
    notifier_id: str,
    payload: NotifierConfigUpdate,
    db: Session = Depends(get_db),
):
    """Update a notifier's configuration."""
    notifier_class = NotifierRegistry.get(notifier_id)

    if not notifier_class:
        raise NotFoundError("Notifier", notifier_id)

    # Merge with existing config, preserving passwords unless explicitly changed
    existing_json = Settings.get(db, f"notification_{notifier_id}_config", "{}")
    try:
        existing_config = json.loads(existing_json) if existing_json else {}
    except json.JSONDecodeError:
        existing_config = {}

    schema = notifier_class.get_config_schema()

    # Merge existing with env vars for validation
    existing_with_env = _get_config_with_env(existing_config, notifier_id, schema)

    # Validate required fields if enabling
    if payload.enabled:
        _validate_config(payload.config, schema, existing_with_env)

    # Filter out empty password fields (empty = keep existing)
    filtered_payload = _filter_empty_passwords(payload.config, schema)
    merged_config = {**existing_config, **filtered_payload}

    # Save settings
    Settings.set_bool(db, f"notification_{notifier_id}_enabled", payload.enabled)
    Settings.set(db, f"notification_{notifier_id}_config", json.dumps(merged_config))

    # Save event settings
    for event_id, event_enabled in payload.events.items():
        Settings.set_bool(
            db, f"notification_{notifier_id}_event_{event_id}", event_enabled
        )

    logger.info(
        "Updated notifier %s: enabled=%s",
        notifier_id,
        payload.enabled,
    )

    # Return masked config (with env vars merged for display)
    config_with_env = _get_config_with_env(merged_config, notifier_id, schema)
    masked_config = _mask_sensitive_fields(config_with_env, schema, notifier_id)

    return {
        "id": notifier_id,
        "enabled": payload.enabled,
        "config": masked_config,
        "events": payload.events,
    }


@router.post("/{notifier_id}/test")
def test_notifier(
    notifier_id: str,
    payload: NotifierTestRequest,
    db: Session = Depends(get_read_db),
):
    """
    Test a notifier connection with the provided configuration.

    This allows testing before saving the configuration.
    """
    notifier_class = NotifierRegistry.get(notifier_id)

    if not notifier_class:
        raise NotFoundError("Notifier", notifier_id)

    # Merge with existing config, preserving passwords unless explicitly changed
    existing_json = Settings.get(db, f"notification_{notifier_id}_config", "{}")
    try:
        existing_config = json.loads(existing_json) if existing_json else {}
    except json.JSONDecodeError:
        existing_config = {}

    schema = notifier_class.get_config_schema()

    # Filter out empty password fields (empty = use existing)
    filtered_payload = _filter_empty_passwords(payload.config, schema)
    merged_config = {**existing_config, **filtered_payload}

    # Merge with environment variables (env vars take precedence)
    test_config = _get_config_with_env(merged_config, notifier_id, schema)

    try:
        notifier = notifier_class(test_config)
        success, message = notifier.test_connection()

        return {"success": success, "message": message}

    except Exception as e:
        logger.error("Error testing notifier %s: %s", notifier_id, e)
        return {"success": False, "message": str(e)}


@router.get("/{notifier_id}/libraries")
def get_notifier_libraries(notifier_id: str, db: Session = Depends(get_read_db)):
    """
    Get available libraries for a notifier (e.g., Plex libraries).

    This endpoint is used to populate dynamic select options.
    """
    notifier_class = NotifierRegistry.get(notifier_id)

    if not notifier_class:
        raise NotFoundError("Notifier", notifier_id)

    config_json = Settings.get(db, f"notification_{notifier_id}_config", "{}")
    try:
        config = json.loads(config_json) if config_json else {}
    except json.JSONDecodeError:
        config = {}

    # Merge with environment variables
    schema = notifier_class.get_config_schema()
    config = _get_config_with_env(config, notifier_id, schema)

    try:
        notifier = notifier_class(config)

        # Check if notifier has get_libraries method
        if hasattr(notifier, "get_libraries"):
            libraries = notifier.get_libraries()
            return {"libraries": libraries}

        return {"libraries": []}

    except Exception as e:
        logger.error("Error fetching libraries for %s: %s", notifier_id, e)
        return {"libraries": [], "error": str(e)}


def _mask_sensitive_fields(config: dict, schema: dict, notifier_id: str) -> dict:
    """
    Remove password field values from config for API responses.

    Instead of sending a mask string, we send an empty string and include
    a 'has_value' flag so the frontend knows if a value is saved.
    Also indicates if the value comes from an environment variable.
    """
    masked = config.copy()

    for field_name, field_schema in schema.items():
        if field_schema.get("type") == "password" and field_name in masked:
            has_value = bool(config.get(field_name))
            from_env = _is_field_from_env(notifier_id, field_name)

            # Don't send the actual value, just indicate if one exists
            masked[field_name] = ""
            masked[f"_{field_name}_set"] = has_value
            masked[f"_{field_name}_env"] = from_env

    return masked


def _filter_empty_passwords(config: dict, schema: dict) -> dict:
    """
    Filter out empty password fields from config before merging.

    Empty strings mean "keep existing value", non-empty means "update".
    """
    filtered = {}
    for key, value in config.items():
        # Skip the _set and _env flags
        if key.startswith("_") and (key.endswith("_set") or key.endswith("_env")):
            continue
        # Skip empty password fields (means "don't change")
        field_schema = schema.get(key, {})
        if field_schema.get("type") == "password" and value == "":
            continue
        filtered[key] = value
    return filtered


def _validate_config(
    config: dict, schema: dict, existing_config: dict | None = None
) -> None:
    """
    Validate config against schema, checking required fields.

    For password fields, also checks existing_config since empty means "keep existing".
    """
    existing = existing_config or {}

    for field_name, field_schema in schema.items():
        if field_schema.get("required", False):
            value = config.get(field_name)
            # For password fields, empty string means "use existing"
            if field_schema.get("type") == "password" and value == "":
                value = existing.get(field_name)
            if not value:
                raise ValidationError(
                    f"Missing required field: {field_schema.get('label', field_name)}"
                )
