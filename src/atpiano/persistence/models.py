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
