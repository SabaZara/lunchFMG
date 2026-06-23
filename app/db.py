"""Database engine, session factory, and one-time initialization.

SQLite specifics:
  * check_same_thread=False so FastAPI's threadpool can share the engine.
  * WAL journal mode + busy_timeout so concurrent taps don't error out on a
    locked file — combined with the UNIQUE constraint this gives correct
    once-per-day behaviour under concurrency.
  * PRAGMA foreign_keys=ON to enforce the FK.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.db_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def init_db() -> None:
    """Create tables if they do not exist. Safe to call repeatedly."""
    # Importing models registers them on SQLModel.metadata.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closed after the request."""
    with Session(engine) as session:
        yield session
