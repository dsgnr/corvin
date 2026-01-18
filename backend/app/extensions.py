"""
Database configuration.

Sets up SQLAlchemy with SQLite.
Uses separate engines for read and write operations to maximise concurrency.
"""

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/corvin.db")

# SQLite needs some special handling for thread safety
connect_args = (
    {"check_same_thread": False, "timeout": 5} if "sqlite" in DATABASE_URL else {}
)

# Main engine for write operations
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

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


if "sqlite" in DATABASE_URL:
    event.listen(engine, "connect", _set_sqlite_pragma)
    event.listen(read_engine, "connect", _set_sqlite_pragma)


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
