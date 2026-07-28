"""Create the family identity catalog.

Revision ID: 20260728_0001
Revises:
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column(
            "normalized_username",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
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
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(normalized_username) BETWEEN 1 AND 64",
            name="ck_users_normalized_username_length",
        ),
        sa.CheckConstraint(
            "length(username) BETWEEN 1 AND 64",
            name="ck_users_username_length",
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint(
            "normalized_username",
            name="uq_users_normalized_username",
        ),
    )
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 200",
            name="ck_workspaces_name_length",
        ),
        sa.CheckConstraint(
            "mode IN ('local', 'cloud', 'synced')",
            name="ck_workspaces_mode",
        ),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_memberships_role",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "workspace_id"),
    )
    op.create_index(
        "ix_memberships_workspace_id",
        "memberships",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "web_sessions",
        sa.Column(
            "web_session_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "idle_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "absolute_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(token_digest) = 64",
            name="ck_web_sessions_token_digest_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("web_session_id"),
        sa.UniqueConstraint(
            "token_digest",
            name="uq_web_sessions_token_digest",
        ),
    )
    op.create_index(
        "ix_web_sessions_absolute_expires_at",
        "web_sessions",
        ["absolute_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_web_sessions_idle_expires_at",
        "web_sessions",
        ["idle_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_web_sessions_user_id",
        "web_sessions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_sessions_user_id",
        table_name="web_sessions",
    )
    op.drop_index(
        "ix_web_sessions_idle_expires_at",
        table_name="web_sessions",
    )
    op.drop_index(
        "ix_web_sessions_absolute_expires_at",
        table_name="web_sessions",
    )
    op.drop_table("web_sessions")
    op.drop_index(
        "ix_memberships_workspace_id",
        table_name="memberships",
    )
    op.drop_table("memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
