"""Catalog location, migration, and idempotent local-workspace setup."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from atpiano.persistence.database import create_catalog_engine
from atpiano.persistence.models import WorkspaceRow

CATALOG_DIRECTORY_NAME = ".atpiano"
CATALOG_FILENAME = "catalog.sqlite3"
LOCAL_WORKSPACE_ID = "local"
LOCAL_WORKSPACE_NAME = "On this device"


def catalog_database_path(workspace_directory: Path) -> Path:
    return (
        workspace_directory.resolve()
        / CATALOG_DIRECTORY_NAME
        / CATALOG_FILENAME
    )


def _alembic_config(*, connection: object | None = None) -> Config:
    repository_root = Path(__file__).resolve().parents[3]
    configuration = Config(str(repository_root / "alembic.ini"))
    configuration.set_main_option(
        "script_location",
        str(Path(__file__).with_name("alembic")),
    )
    if connection is not None:
        configuration.attributes["connection"] = connection
    return configuration


def upgrade_catalog(engine: Engine, revision: str = "head") -> None:
    with engine.begin() as connection:
        command.upgrade(
            _alembic_config(connection=connection),
            revision,
        )


def catalog_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def catalog_head_revision() -> str:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("the catalog migration history has no head")
    return head


def _ensure_local_workspace(engine: Engine) -> None:
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        workspace = session.get(WorkspaceRow, LOCAL_WORKSPACE_ID)
        if workspace is None:
            session.add(
                WorkspaceRow(
                    workspace_id=LOCAL_WORKSPACE_ID,
                    name=LOCAL_WORKSPACE_NAME,
                    mode="local",
                    created_at=now,
                )
            )
            return
        if workspace.mode != "local":
            raise RuntimeError(
                "the reserved local workspace has an incompatible mode"
            )


def initialize_catalog(workspace_directory: Path) -> tuple[Path, Engine]:
    database_path = catalog_database_path(workspace_directory)
    engine = create_catalog_engine(database_path)
    try:
        upgrade_catalog(engine)
        _ensure_local_workspace(engine)
    except BaseException:
        engine.dispose()
        raise
    return database_path, engine
