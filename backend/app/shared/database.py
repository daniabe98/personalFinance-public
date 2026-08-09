"""Synchronous SQLAlchemy and SQLite configuration."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative metadata shared by persistence adapters and Alembic."""


SessionFactory = Callable[[], Session]


def create_engine(database_url: str, *, busy_timeout_ms: int = 5_000) -> Engine:
    """Create a SQLite engine with integrity and contention safeguards."""
    engine = sqlalchemy_create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(
        dbapi_connection: DBAPIConnection,
        _connection_record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute(f"PRAGMA busy_timeout = {busy_timeout_ms:d}")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build an injected, non-autocommitting session factory."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def database_is_ready(engine: Engine) -> bool:
    """Probe an already configured engine."""
    with Connection(engine) as connection:
        connection.exec_driver_sql("SELECT 1")
    return True


__all__ = (
    "Base",
    "SessionFactory",
    "create_engine",
    "create_session_factory",
    "database_is_ready",
)
