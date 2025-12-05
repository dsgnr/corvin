import logging

from flask import Flask

from app.core.logging import setup_logging, get_logger
from app.extensions import db, migrate, scheduler

logger = get_logger("app")


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    setup_logging(level=logging.INFO)

    app = Flask(__name__)
    app.url_map.strict_slashes = False
    _configure_app(app, config)

    db.init_app(app)
    migrate.init_app(app, db)

    _register_blueprints(app)

    with app.app_context():
        db.create_all()
        _reset_stale_tasks()
        _init_worker(app)
        _setup_scheduler(app)

    logger.info("Application initialised")
    return app


def _configure_app(app: Flask, config: dict | None) -> None:
    """Configure application settings."""
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////data/corvin.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_SYNC_WORKERS"] = 2
    app.config["MAX_DOWNLOAD_WORKERS"] = 3

    if config:
        app.config.update(config)


def _register_blueprints(app: Flask) -> None:
    """Register all route blueprints."""
    from app.routes import profiles, lists, videos, history, tasks, errors

    app.register_blueprint(profiles.bp)
    app.register_blueprint(lists.bp)
    app.register_blueprint(videos.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(errors.bp)


def _reset_stale_tasks() -> None:
    """Reset any tasks stuck in RUNNING state from previous run."""
    from app.models.task import Task, TaskStatus

    count = Task.query.filter_by(status=TaskStatus.RUNNING.value).update(
        {"status": TaskStatus.PENDING.value, "started_at": None}
    )
    db.session.commit()

    if count:
        logger.info("Reset %d stale tasks to pending", count)


def _init_worker(app: Flask) -> None:
    """Set up the background task worker and register handlers."""
    from app.task_queue import init_worker
    from app.tasks import sync_single_list, download_single_video
    from app.models.task import TaskType

    worker = init_worker(
        app,
        max_sync_workers=app.config["MAX_SYNC_WORKERS"],
        max_download_workers=app.config["MAX_DOWNLOAD_WORKERS"],
    )
    worker.register_handler(TaskType.SYNC.value, sync_single_list)
    worker.register_handler(TaskType.DOWNLOAD.value, download_single_video)
    worker.start()


def _setup_scheduler(app: Flask) -> None:
    """Set up periodic task scheduling for syncs and downloads."""
    from app.tasks import schedule_all_syncs, schedule_pending_downloads

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
        func=run_in_context(schedule_pending_downloads),
        trigger="interval",
        minutes=5,
        id="download_videos",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")
