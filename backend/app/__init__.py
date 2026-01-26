"""
Corvin
"""

import os
from contextlib import asynccontextmanager

from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger("app")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from scalar_fastapi import get_scalar_api_reference  # noqa: E402

from app.core.helpers import _get_pyproject_attr  # noqa: E402
from app.extensions import SessionLocal, engine  # noqa: E402
from app.metrics import init_metrics  # noqa: E402
from app.models import Base  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the application lifecycle.

    Startup: initialises database, starts background workers, schedules periodic jobs.
    Shutdown: gracefully stops scheduler and worker threads.
    """
    logger.info("Application starting up...")
    _init_database(app)

    if not app.state.testing:
        _init_worker(app)
        _setup_scheduler(app)

    logger.info("Application ready")
    yield

    logger.info("Application shutting down...")
    _shutdown(app)


def create_app(config: dict | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Optional configuration overrides. Set TESTING=True to skip
                worker/scheduler initialisation.

    Returns:
        Configured FastAPI application instance.
    """
    debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    app = FastAPI(
        title=_get_pyproject_attr("name"),
        version=_get_pyproject_attr("version"),
        description=_get_pyproject_attr("description"),
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        debug=debug,
        redirect_slashes=False,
    )

    app.state.testing = config.get("TESTING", False) if config else False
    app.state.config = _build_config(config)

    _add_middleware(app)
    _register_routes(app)
    _register_exception_handlers(app)
    _register_scalar_docs(app)
    init_metrics(app)

    return app


def _build_config(config: dict | None) -> dict:
    """
    Build application configuration by merging defaults with overrides.

    Defaults are suitable for local development. Override via environment
    variables or by passing a config dict.
    """
    default_config = {
        "SQLALCHEMY_DATABASE_URI": "sqlite:////data/corvin.db",
        "MAX_SYNC_WORKERS": int(os.getenv("MAX_SYNC_WORKERS", "2")),
        "MAX_DOWNLOAD_WORKERS": int(os.getenv("MAX_DOWNLOAD_WORKERS", "2")),
    }
    if config:
        default_config.update(config)
    return default_config


def _add_middleware(app: FastAPI) -> None:
    """
    Add middleware to the application.

    Configures permissive CORS for local network use.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=86400,
    )


def _register_routes(app: FastAPI) -> None:
    """Register all API route routers and the health check endpoint."""
    from app.routes import (
        errors,
        history,
        lists,
        notifications,
        profiles,
        progress,
        schedules,
        tasks,
        videos,
    )

    app.include_router(profiles.router)
    app.include_router(lists.router)
    app.include_router(videos.router)
    app.include_router(history.router)
    app.include_router(tasks.router)
    app.include_router(progress.router)
    app.include_router(schedules.router)
    app.include_router(notifications.router)
    errors.register_exception_handlers(app)

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "healthy"}


def _register_scalar_docs(app: FastAPI) -> None:
    """Register Scalar API documentation."""

    @app.get("/api/docs", include_in_schema=False)
    async def scalar_docs():
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=app.title,
        )


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for AppError and validation errors."""
    from app.core.exceptions import AppError

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "Validation error", "details": exc.errors()},
        )


def _init_database(app: FastAPI) -> None:
    """
    Initialise database schema and reset stale tasks.

    Runs Alembic migrations, then resets any tasks left in "running" state
    from a previous shutdown back to "pending".
    """
    from app.models.task import Task, TaskStatus

    Base.metadata.create_all(bind=engine)

    if not app.state.testing:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception:
            pass

        with SessionLocal() as db:
            db.query(Task).filter_by(status=TaskStatus.RUNNING.value).update(
                {"status": TaskStatus.PENDING.value, "started_at": None}
            )
            db.commit()


def _init_worker(app: FastAPI) -> None:
    """
    Set up the background task worker and register handlers.

    Uses separate thread pools for sync and download tasks to prevent
    long-running downloads from blocking sync operations.
    """
    from app.models.task import TaskType
    from app.task_queue import init_worker
    from app.tasks import download_single_video, sync_single_list

    config = app.state.config
    worker = init_worker(
        max_sync_workers=config["MAX_SYNC_WORKERS"],
        max_download_workers=config["MAX_DOWNLOAD_WORKERS"],
    )
    worker.register_handler(TaskType.SYNC.value, sync_single_list)
    worker.register_handler(TaskType.DOWNLOAD.value, download_single_video)
    worker.start()


def _setup_scheduler(app: FastAPI) -> None:
    """
    Set up periodic task scheduling.

    - Syncs: every 30 minutes (checks for new videos)
    - Downloads: every 5 minutes (processes pending videos)

    Manual triggers are also available via the API.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.tasks import schedule_all_syncs, schedule_downloads

    scheduler = BackgroundScheduler()
    app.state.scheduler = scheduler

    scheduler.add_job(
        func=schedule_all_syncs,
        trigger="interval",
        minutes=30,
        id="sync_videos",
        replace_existing=True,
    )
    scheduler.add_job(
        func=schedule_downloads,
        trigger="interval",
        minutes=5,
        id="download_videos",
        replace_existing=True,
    )

    scheduler.start()


def _shutdown(app: FastAPI) -> None:
    """Gracefully shut down the scheduler and worker threads."""
    from app.task_queue import get_worker

    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown(wait=False)

    worker = get_worker()
    if worker:
        worker.stop()
