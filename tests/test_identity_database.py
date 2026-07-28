from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from atpiano.persistence.catalog import (
    catalog_head_revision,
    catalog_revision,
    initialize_catalog,
)
from atpiano.persistence.models import MembershipRow, WorkspaceRow


def test_empty_catalog_migrates_to_head_and_seeds_local_workspace(
    tmp_path: Path,
) -> None:
    database_path, engine = initialize_catalog(tmp_path)
    try:
        assert database_path == tmp_path / ".atpiano" / "catalog.sqlite3"
        assert catalog_revision(engine) == catalog_head_revision()
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "memberships",
            "users",
            "web_sessions",
            "workspaces",
        }
        with Session(engine) as session:
            workspace = session.get(WorkspaceRow, "local")
            assert workspace is not None
            assert workspace.name == "On this device"
            assert workspace.mode == "local"
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
    finally:
        engine.dispose()


def test_catalog_initialization_is_idempotent(tmp_path: Path) -> None:
    first_path, first_engine = initialize_catalog(tmp_path)
    first_engine.dispose()

    second_path, second_engine = initialize_catalog(tmp_path)
    try:
        assert second_path == first_path
        with Session(second_engine) as session:
            assert session.query(WorkspaceRow).count() == 1
    finally:
        second_engine.dispose()


def test_catalog_enforces_membership_foreign_keys_and_roles(
    tmp_path: Path,
) -> None:
    _, engine = initialize_catalog(tmp_path)
    try:
        with Session(engine) as session, session.begin():
            now = datetime.now(timezone.utc)
            session.add(
                MembershipRow(
                    user_id="user:missing",
                    workspace_id="local",
                    role="owner",
                    created_at=now,
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()


def test_catalog_normalized_usernames_are_unique(tmp_path: Path) -> None:
    _, engine = initialize_catalog(tmp_path)
    try:
        with sqlite3.connect(tmp_path / ".atpiano" / "catalog.sqlite3") as db:
            values = (
                "user:one",
                "Alice",
                "alice",
                "Alice",
                "hash",
                "2026-07-28 10:00:00",
                "2026-07-28 10:00:00",
                "2026-07-28 10:00:00",
            )
            db.execute(
                """
                INSERT INTO users (
                    user_id, username, normalized_username, display_name,
                    password_hash, disabled, created_at, updated_at,
                    password_changed_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                values,
            )
            with pytest.raises(
                sqlite3.IntegrityError,
                match="normalized_username",
            ):
                db.execute(
                    """
                    INSERT INTO users (
                        user_id, username, normalized_username, display_name,
                        password_hash, disabled, created_at, updated_at,
                        password_changed_at
                    ) VALUES (
                        'user:two', 'ALICE', 'alice', 'ALICE', 'hash', 0,
                        '2026-07-28 10:00:00', '2026-07-28 10:00:00',
                        '2026-07-28 10:00:00'
                    )
                    """
                )
    finally:
        engine.dispose()


def test_persistence_models_do_not_leak_into_application_package() -> None:
    application_root = (
        Path(__file__).parents[1] / "src" / "atpiano" / "application"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in application_root.glob("*.py")
    )

    assert "atpiano.persistence" not in source
    assert "sqlalchemy" not in source
    assert "fastapi" not in source
