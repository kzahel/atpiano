from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from atpiano.application.identity import self_profile_id
from atpiano.persistence.catalog import (
    HOME_GROUP_ID,
    catalog_head_revision,
    catalog_revision,
    initialize_catalog,
    upgrade_catalog,
)
from atpiano.persistence.database import create_catalog_engine
from atpiano.persistence.models import (
    GroupMembershipRow,
    GroupProfileRow,
    GroupRow,
    MembershipRow,
    ProfileControllerRow,
    ProfileRow,
    WorkspaceRow,
)


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
            "group_memberships",
            "group_profiles",
            "groups",
            "profile_controllers",
            "profiles",
            "users",
            "web_sessions",
            "workspace_group_grants",
            "workspaces",
        }
        with Session(engine) as session:
            workspace = session.get(WorkspaceRow, "local")
            assert workspace is not None
            assert workspace.name == "Family recordings"
            assert workspace.mode == "local"
            assert workspace.administrative_group_id == HOME_GROUP_ID
            assert workspace.storage_key == "."
            group = session.get(GroupRow, HOME_GROUP_ID)
            assert group is not None
            assert group.name == "Family"
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
    finally:
        engine.dispose()


def test_v1_catalog_backfills_family_group_and_self_profile(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    engine = create_catalog_engine(database_path)
    created_at = datetime(2026, 7, 28, tzinfo=timezone.utc)
    try:
        upgrade_catalog(engine, "20260728_0001")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO workspaces (
                        workspace_id, name, mode, created_at
                    ) VALUES (
                        'local', 'On this device', 'local', :created_at
                    )
                    """
                ),
                {"created_at": created_at},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        user_id, username, normalized_username, display_name,
                        password_hash, disabled, created_at, updated_at,
                        password_changed_at
                    ) VALUES (
                        'user:kyle', 'kyle', 'kyle', 'Kyle', 'hash', 0,
                        :created_at, :created_at, :created_at
                    )
                    """
                ),
                {"created_at": created_at},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO memberships (
                        workspace_id, user_id, role, created_at
                    ) VALUES ('local', 'user:kyle', 'owner', :created_at)
                    """
                ),
                {"created_at": created_at},
            )

        upgrade_catalog(engine)

        profile_id = self_profile_id("user:kyle")
        with Session(engine) as session:
            workspace = session.get(WorkspaceRow, "local")
            assert workspace is not None
            assert workspace.administrative_group_id == HOME_GROUP_ID
            assert workspace.home_profile_id == profile_id
            assert workspace.name == "Family recordings"
            assert workspace.created_by_user_id == "user:kyle"
            assert workspace.storage_key == "."
            membership = session.get(
                GroupMembershipRow,
                (HOME_GROUP_ID, "user:kyle"),
            )
            assert membership is not None
            assert membership.role == "owner"
            profile = session.get(ProfileRow, profile_id)
            assert profile is not None
            assert profile.display_name == "Kyle"
            assert session.get(
                ProfileControllerRow,
                (profile_id, "user:kyle"),
            ) is not None
            assert session.get(
                GroupProfileRow,
                (HOME_GROUP_ID, profile_id),
            ) is not None
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
