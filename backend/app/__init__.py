import atexit
import logging
import os

from flask import Response, json
from flask_cors import CORS
from flask_openapi3 import Info, OpenAPI
from pydantic import ValidationError

from app.core.helpers import _get_pyproject_attr
from app.core.logging import get_logger, setup_logging
from app.extensions import db, migrate, scheduler
from app.metrics import init_metrics

logger = get_logger("app")

info = Info(
    title=_get_pyproject_attr("name"),
    version=_get_pyproject_attr("version"),
    description=_get_pyproject_attr("description"),
)


def _validation_error_callback(e: ValidationError) -> Response:
    """Return 400 instead of 422 for Pydantic validation errors."""
    return Response(
        json.dumps({"message": "Validation error", "errors": e.errors()}),
        status=400,
        mimetype="application/json",
    )


def create_app(config: dict | None = None) -> OpenAPI:
    """Create and configure the Flask application."""
    setup_logging(level=logging.INFO)

    app = OpenAPI(
        __name__,
        info=info,
        doc_prefix="/api/docs",
        validation_error_callback=_validation_error_callback,
    )
    app.url_map.strict_slashes = False

    _configure_app(app, config)
    _init_extensions(app)
    _register_blueprints(app)

    with app.app_context():
        _init_database(app)
        if not app.config.get("TESTING") and not _in_reloader_parent():
            _init_worker(app)
            _setup_scheduler(app)

    logger.info("Application initialised")
    return app


def _in_reloader_parent() -> bool:
    """Check if running in Flask's debug reloader parent process.

    Flask's debug reloader spawns two processes - skip the parent to avoid
    duplicate workers. Gunicorn doesn't set FLASK_DEBUG so this is a no-op.
    """
    return (
        os.environ.get("FLASK_DEBUG") == "1"
        and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    )


def _configure_app(app: OpenAPI, config: dict | None) -> None:
    """Configure application settings."""
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////data/corvin.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_SYNC_WORKERS"] = int(os.getenv("MAX_SYNC_WORKERS", "2"))
    app.config["MAX_DOWNLOAD_WORKERS"] = int(os.getenv("MAX_DOWNLOAD_WORKERS", "2"))

    if config:
        app.config.update(config)


def _init_extensions(app: OpenAPI) -> None:
    """Initialise Flask extensions."""
    CORS(app, resources={r"/*": {"origins": "*", "max_age": 86400}})
    db.init_app(app)
    migrate.init_app(app, db)
    init_metrics(app)


def _register_blueprints(app: OpenAPI) -> None:
    """Register all route blueprints."""
    from app.routes import errors, history, lists, profiles, progress, tasks, videos

    app.register_api(profiles.bp)
    app.register_api(lists.bp)
    app.register_api(videos.bp)
    app.register_api(history.bp)
    app.register_api(tasks.bp)
    app.register_api(progress.bp)
    app.register_blueprint(errors.bp)


def _init_database(app: OpenAPI) -> None:
    """Initialise database schema and reset stale tasks."""
    from flask_migrate import upgrade

    from app.models.task import Task, TaskStatus

    db.create_all()

    if not app.config.get("TESTING"):
        upgrade()

        # Reset any tasks stuck in RUNNING state from previous run
        count = Task.query.filter_by(status=TaskStatus.RUNNING.value).update(
            {"status": TaskStatus.PENDING.value, "started_at": None}
        )
        db.session.commit()
        if count:
            logger.info("Reset %d stale tasks to pending", count)


def _init_worker(app: OpenAPI) -> None:
    """Set up the background task worker and register handlers."""
    from app.models.task import TaskType
    from app.task_queue import init_worker
    from app.tasks import download_single_video, sync_single_list

    worker = init_worker(
        app,
        max_sync_workers=app.config["MAX_SYNC_WORKERS"],
        max_download_workers=app.config["MAX_DOWNLOAD_WORKERS"],
    )
    worker.register_handler(TaskType.SYNC.value, sync_single_list)
    worker.register_handler(TaskType.DOWNLOAD.value, download_single_video)
    worker.start()


def _setup_scheduler(app: OpenAPI) -> None:
    """Set up periodic task scheduling for syncs and downloads."""
    from app.tasks import schedule_all_syncs, schedule_downloads

    def run_in_context(func):
        def wrapper():
            with app.app_context():
                func()

        return wrapper

    scheduler.add_job(
        func=run_in_context(schedule_all_syncs),
        trigger="interval",
        minutes=30,
        id="sync_videos",
        replace_existing=True,
    )
    scheduler.add_job(
        func=run_in_context(schedule_downloads),
        trigger="interval",
        minutes=5,
        id="download_videos",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")
        atexit.register(lambda: scheduler.shutdown(wait=False))
