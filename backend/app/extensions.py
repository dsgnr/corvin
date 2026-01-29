"""
Database configuration.

Supports both SQLite (default) and PostgreSQL.
Uses separate engines for read and write operations to maximise concurrency.

PostgreSQL is used when POSTGRES_HOST is set. Otherwise, falls back to SQLite.
"""

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


def _build_database_url() -> str:
    """
    Build the database URL from environment variables.

    PostgreSQL is used when POSTGRES_HOST is defined.
    Falls back to SQLite otherwise.
    Password is optional.
    """
    postgres_host = os.getenv("POSTGRES_HOST")

    if postgres_host:
        postgres_user = quote_plus(os.getenv("POSTGRES_USER", "corvin"))
        postgres_password = os.getenv("POSTGRES_PASSWORD")  # optional
        postgres_db = os.getenv("POSTGRES_DB", "corvin")
        postgres_port = os.getenv("POSTGRES_PORT", "5432")

        # Build URL with optional password
        if postgres_password:
            postgres_password = quote_plus(postgres_password)
            auth = f"{postgres_user}:{postgres_password}"
        else:
            auth = postgres_user

        return f"postgresql+psycopg2://{auth}@{postgres_host}:{postgres_port}/{postgres_db}"

    return os.getenv("DATABASE_URL", "sqlite:////data/corvin.db")


DATABASE_URL = _build_database_url()

# SQLite needs special connect_args for thread safety
# Use POSTGRES_HOST as the source of truth (same as _build_database_url)
_use_postgres = bool(os.getenv("POSTGRES_HOST"))
connect_args = {} if _use_postgres else {"check_same_thread": False, "timeout": 5}

# Main engine for write operations
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Database dialect from engine
DB_DIALECT = engine.dialect.name

# Read-only engine for queries (separate connection pool)
read_engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    execution_options={"isolation_level": "AUTOCOMMIT"},
)


def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure SQLite for better performance and concurrency."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA locking_mode=NORMAL")
    cursor.execute("PRAGMA wal_autocheckpoint=1000")
    cursor.execute("PRAGMA busy_timeout=60000")  # 60 seconds
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.close()


if DB_DIALECT == "sqlite":
    event.listen(engine, "connect", _set_sqlite_pragma)
    event.listen(read_engine, "connect", _set_sqlite_pragma)


def json_text(column):
    """
    Return a column expression suitable for text operations on JSON.

    SQLite stores JSON as text natively, so no cast needed.
    PostgreSQL requires casting to text for LIKE/ILIKE operations.
    """
    if DB_DIALECT == "sqlite":
        return column
    from sqlalchemy import cast
    from sqlalchemy.types import String

    return cast(column, String)


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

# Read-only session - uses AUTOCOMMIT to avoid holding read locks
ReadSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=read_engine, expire_on_commit=False
)

# Shared executor for SSE database operations
sse_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="sse_db")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session for write operations.

    Yields:
        A SQLAlchemy session, automatically closed when the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a read-only database session.

    Uses AUTOCOMMIT isolation to avoid holding read locks during concurrent writes.
    Use this for GET endpoints that don't need to write data.

    Yields:
        A SQLAlchemy session, automatically closed when the request completes.
    """
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()
