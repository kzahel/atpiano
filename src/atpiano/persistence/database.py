"""SQLAlchemy engine and session configuration for the local catalog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text

CatalogSession = sessionmaker[Session]


def _sqlite_url(database_path: Path) -> URL:
    return URL.create(
        drivername="sqlite+pysqlite",
        database=str(database_path.resolve()),
    )


def create_catalog_engine(database_path: Path) -> Engine:
    """Create one short-transaction SQLite engine for the catalog."""

    resolved = database_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    engine = EngineFactory.create(_sqlite_url(resolved))
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return engine


class EngineFactory:
    """Centralize SQLite connection policy for migrations and repositories."""

    @staticmethod
    def create(url: URL) -> Engine:
        from sqlalchemy import create_engine

        engine = create_engine(
            url,
            poolclass=NullPool,
            future=True,
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(
            dbapi_connection: sqlite3.Connection,
            _connection_record: object,
        ) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA busy_timeout = 5000")
                cursor.execute("PRAGMA journal_mode = WAL")
            finally:
                cursor.close()

        return engine


def catalog_session_factory(engine: Engine) -> CatalogSession:
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
