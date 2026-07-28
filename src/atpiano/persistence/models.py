"""Typed SQLAlchemy models for identity and browser sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "length(username) BETWEEN 1 AND 64",
            name="ck_users_username_length",
        ),
        CheckConstraint(
            "length(normalized_username) BETWEEN 1 AND 64",
            name="ck_users_normalized_username_length",
        ),
        UniqueConstraint(
            "normalized_username",
            name="uq_users_normalized_username",
        ),
    )

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    normalized_username: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(Text)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )


class GroupRow(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('household', 'studio', 'friends', 'other')",
            name="ck_groups_kind",
        ),
        CheckConstraint(
            "default_space_audience IN ('group', 'controllers')",
            name="ck_groups_default_space_audience",
        ),
        CheckConstraint(
            "default_space_role IN ('editor', 'viewer')",
            name="ck_groups_default_space_role",
        ),
        CheckConstraint(
            "length(name) BETWEEN 1 AND 200",
            name="ck_groups_name_length",
        ),
    )

    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    default_space_audience: Mapped[str] = mapped_column(String(16))
    default_space_role: Mapped[str] = mapped_column(String(16))
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class GroupMembershipRow(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_group_memberships_role",
        ),
        Index("ix_group_memberships_user_id", "user_id"),
    )

    group_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProfileRow(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "length(display_name) BETWEEN 1 AND 128",
            name="ck_profiles_display_name_length",
        ),
    )

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProfileControllerRow(Base):
    __tablename__ = "profile_controllers"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'manager')",
            name="ck_profile_controllers_role",
        ),
        Index("ix_profile_controllers_user_id", "user_id"),
    )

    profile_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("profiles.profile_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GroupProfileRow(Base):
    __tablename__ = "group_profiles"

    group_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("profiles.profile_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceRow(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('local', 'cloud', 'synced')",
            name="ck_workspaces_mode",
        ),
        CheckConstraint(
            "length(name) BETWEEN 1 AND 200",
            name="ck_workspaces_name_length",
        ),
    )

    workspace_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    administrative_group_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("groups.group_id", ondelete="RESTRICT"),
        nullable=True,
    )
    home_profile_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("profiles.profile_id", ondelete="SET NULL"),
        nullable=True,
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class MembershipRow(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_memberships_role",
        ),
        Index("ix_memberships_workspace_id", "workspace_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceGroupGrantRow(Base):
    __tablename__ = "workspace_group_grants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('editor', 'viewer')",
            name="ck_workspace_group_grants_role",
        ),
        Index("ix_workspace_group_grants_group_id", "group_id"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    granted_by_user_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebSessionRow(Base):
    __tablename__ = "web_sessions"
    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_web_sessions_token_digest",
        ),
        CheckConstraint(
            "length(token_digest) = 64",
            name="ck_web_sessions_token_digest_length",
        ),
        Index("ix_web_sessions_user_id", "user_id"),
        Index("ix_web_sessions_idle_expires_at", "idle_expires_at"),
        Index(
            "ix_web_sessions_absolute_expires_at",
            "absolute_expires_at",
        ),
    )

    web_session_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )
    token_digest: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
