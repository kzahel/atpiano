"""Add generic groups, managed profiles, and workspace grants.

Revision ID: 20260728_0002
Revises: 20260728_0001
Create Date: 2026-07-28
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0002"
down_revision: str | Sequence[str] | None = "20260728_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOME_GROUP_ID = "group:home"


def _self_profile_id(user_id: str) -> str:
    value = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://atpiano.local/profile/{user_id}",
    )
    return f"profile:{value.hex}"


def upgrade() -> None:
    connection = op.get_bind()
    legacy_memberships = tuple(
        connection.execute(
            sa.text(
                """
                SELECT workspace_id, user_id, role, created_at
                FROM memberships
                """
            )
        ).mappings()
    )
    op.create_table(
        "groups",
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "default_space_audience",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "default_space_role",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "kind IN ('household', 'studio', 'friends', 'other')",
            name="ck_groups_kind",
        ),
        sa.CheckConstraint(
            "default_space_audience IN ('group', 'controllers')",
            name="ck_groups_default_space_audience",
        ),
        sa.CheckConstraint(
            "default_space_role IN ('editor', 'viewer')",
            name="ck_groups_default_space_role",
        ),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 200",
            name="ck_groups_name_length",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("group_id"),
    )
    op.create_table(
        "group_memberships",
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_group_memberships_role",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.group_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "user_id"),
    )
    op.create_index(
        "ix_group_memberships_user_id",
        "group_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "profiles",
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "disabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 128",
            name="ck_profiles_display_name_length",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.create_table(
        "profile_controllers",
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'manager')",
            name="ck_profile_controllers_role",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.profile_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("profile_id", "user_id"),
    )
    op.create_index(
        "ix_profile_controllers_user_id",
        "profile_controllers",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "group_profiles",
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.group_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.profile_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "profile_id"),
    )

    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(
            sa.Column(
                "administrative_group_id",
                sa.String(length=128),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "home_profile_id",
                sa.String(length=128),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "storage_key",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "created_by_user_id",
                sa.String(length=128),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "archived_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.create_foreign_key(
            "fk_workspaces_administrative_group_id_groups",
            "groups",
            ["administrative_group_id"],
            ["group_id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_workspaces_home_profile_id_profiles",
            "profiles",
            ["home_profile_id"],
            ["profile_id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_workspaces_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["user_id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_workspaces_storage_key",
            ["storage_key"],
        )

    for membership in legacy_memberships:
        connection.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO memberships (
                    workspace_id, user_id, role, created_at
                ) VALUES (
                    :workspace_id, :user_id, :role, :created_at
                )
                """
            ),
            dict(membership),
        )

    op.create_table(
        "workspace_group_grants",
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "granted_by_user_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('editor', 'viewer')",
            name="ck_workspace_group_grants_role",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.group_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "group_id"),
    )
    op.create_index(
        "ix_workspace_group_grants_group_id",
        "workspace_group_grants",
        ["group_id"],
        unique=False,
    )

    now = datetime.now(timezone.utc)
    owner_id = connection.scalar(
        sa.text(
            """
            SELECT m.user_id
            FROM memberships AS m
            JOIN users AS u ON u.user_id = m.user_id
            WHERE m.workspace_id = 'local'
              AND m.role = 'owner'
              AND u.disabled = 0
            ORDER BY m.created_at, m.user_id
            LIMIT 1
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO groups (
                group_id, name, kind, default_space_audience,
                default_space_role, created_by_user_id, created_at,
                updated_at, archived_at
            ) VALUES (
                :group_id, 'Family', 'household', 'group', 'editor',
                :owner_id, :now, :now, NULL
            )
            """
        ),
        {"group_id": HOME_GROUP_ID, "owner_id": owner_id, "now": now},
    )
    workspaces = connection.execute(
        sa.text(
            """
            SELECT workspace_id, created_at
            FROM workspaces
            ORDER BY workspace_id
            """
        )
    ).mappings()
    for workspace in workspaces:
        workspace_id = str(workspace["workspace_id"])
        creator_id = connection.scalar(
            sa.text(
                """
                SELECT user_id
                FROM memberships
                WHERE workspace_id = :workspace_id AND role = 'owner'
                ORDER BY created_at, user_id
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id},
        )
        storage_key = "." if workspace_id == "local" else f"legacy:{workspace_id}"
        connection.execute(
            sa.text(
                """
                UPDATE workspaces
                SET administrative_group_id = :group_id,
                    name = CASE
                        WHEN name = 'On this device'
                        THEN 'Family recordings'
                        ELSE name
                    END,
                    storage_key = :storage_key,
                    created_by_user_id = :creator_id,
                    updated_at = created_at
                WHERE workspace_id = :workspace_id
                """
            ),
            {
                "group_id": HOME_GROUP_ID,
                "storage_key": storage_key,
                "creator_id": creator_id,
                "workspace_id": workspace_id,
            },
        )
    users = tuple(
        connection.execute(
            sa.text(
                """
                SELECT DISTINCT u.user_id, u.display_name, u.created_at
                FROM users AS u
                JOIN memberships AS m ON m.user_id = u.user_id
                ORDER BY u.user_id
                """
            )
        ).mappings()
    )
    for user in users:
        user_id = str(user["user_id"])
        created_at = user["created_at"]
        group_role = (
            "owner"
            if connection.scalar(
                sa.text(
                    """
                    SELECT 1
                    FROM memberships
                    WHERE user_id = :user_id AND role = 'owner'
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            )
            else "member"
        )
        profile_id = _self_profile_id(user_id)
        connection.execute(
            sa.text(
                """
                INSERT INTO group_memberships (
                    group_id, user_id, role, created_at
                ) VALUES (:group_id, :user_id, :role, :created_at)
                """
            ),
            {
                "group_id": HOME_GROUP_ID,
                "user_id": user_id,
                "role": group_role,
                "created_at": created_at,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO profiles (
                    profile_id, display_name, created_by_user_id,
                    disabled, created_at, updated_at
                ) VALUES (
                    :profile_id, :display_name, :user_id,
                    0, :created_at, :created_at
                )
                """
            ),
            {
                "profile_id": profile_id,
                "display_name": str(user["display_name"]),
                "user_id": user_id,
                "created_at": created_at,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO profile_controllers (
                    profile_id, user_id, role, created_at
                ) VALUES (:profile_id, :user_id, 'owner', :created_at)
                """
            ),
            {
                "profile_id": profile_id,
                "user_id": user_id,
                "created_at": created_at,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO group_profiles (
                    group_id, profile_id, created_at
                ) VALUES (:group_id, :profile_id, :created_at)
                """
            ),
            {
                "group_id": HOME_GROUP_ID,
                "profile_id": profile_id,
                "created_at": created_at,
            },
        )
    connection.execute(
        sa.text(
            """
            UPDATE workspaces
            SET home_profile_id = (
                SELECT pc.profile_id
                FROM memberships AS m
                JOIN profile_controllers AS pc
                  ON pc.user_id = m.user_id
                 AND pc.role = 'owner'
                WHERE m.workspace_id = workspaces.workspace_id
                  AND m.role = 'owner'
                ORDER BY m.created_at, m.user_id
                LIMIT 1
            )
            WHERE home_profile_id IS NULL
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    memberships = tuple(
        connection.execute(
            sa.text(
                """
                SELECT workspace_id, user_id, role, created_at
                FROM memberships
                """
            )
        ).mappings()
    )
    op.drop_index(
        "ix_workspace_group_grants_group_id",
        table_name="workspace_group_grants",
    )
    op.drop_table("workspace_group_grants")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint(
            "uq_workspaces_storage_key",
            type_="unique",
        )
        batch.drop_constraint(
            "fk_workspaces_created_by_user_id_users",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_workspaces_home_profile_id_profiles",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_workspaces_administrative_group_id_groups",
            type_="foreignkey",
        )
        batch.drop_column("archived_at")
        batch.drop_column("updated_at")
        batch.drop_column("created_by_user_id")
        batch.drop_column("storage_key")
        batch.drop_column("home_profile_id")
        batch.drop_column("administrative_group_id")
    for membership in memberships:
        connection.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO memberships (
                    workspace_id, user_id, role, created_at
                ) VALUES (
                    :workspace_id, :user_id, :role, :created_at
                )
                """
            ),
            dict(membership),
        )
    op.drop_table("group_profiles")
    op.drop_index(
        "ix_profile_controllers_user_id",
        table_name="profile_controllers",
    )
    op.drop_table("profile_controllers")
    op.drop_table("profiles")
    op.drop_index(
        "ix_group_memberships_user_id",
        table_name="group_memberships",
    )
    op.drop_table("group_memberships")
    op.drop_table("groups")
