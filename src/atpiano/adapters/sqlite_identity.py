"""SQLAlchemy implementation of the identity repository port."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from atpiano.application.errors import (
    ApplicationConflictError,
    AuthenticationError,
)
from atpiano.application.identity import (
    IdentityUser,
    Principal,
    StoredCredentials,
    WorkspaceMembership,
)
from atpiano.contracts.schemas import MembershipRole
from atpiano.persistence.models import (
    MembershipRow,
    UserRow,
    WebSessionRow,
    WorkspaceRow,
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _memberships(
    session: Session,
    user_id: str,
) -> tuple[WorkspaceMembership, ...]:
    rows = session.scalars(
        select(MembershipRow)
        .where(MembershipRow.user_id == user_id)
        .order_by(MembershipRow.workspace_id)
    )
    return tuple(
        WorkspaceMembership(
            workspace_id=row.workspace_id,
            role=MembershipRole(row.role),
            created_at=_aware(row.created_at),
        )
        for row in rows
    )


def _identity_user(session: Session, row: UserRow) -> IdentityUser:
    return IdentityUser(
        user_id=row.user_id,
        username=row.username,
        display_name=row.display_name,
        disabled=row.disabled,
        created_at=_aware(row.created_at),
        memberships=_memberships(session, row.user_id),
    )


def _principal(session: Session, row: UserRow) -> Principal:
    user = _identity_user(session, row)
    return Principal(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        memberships=user.memberships,
    )


class SqlAlchemyIdentityRepository:
    """Short-transaction relational identity operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_user(
        self,
        *,
        user_id: str,
        username: str,
        normalized_username: str,
        display_name: str,
        password_hash: str,
        workspace_id: str,
        role: MembershipRole,
        now: datetime,
    ) -> IdentityUser:
        try:
            with Session(self._engine) as session, session.begin():
                if session.get(WorkspaceRow, workspace_id) is None:
                    raise ApplicationConflictError(
                        "workspace does not exist"
                    )
                row = UserRow(
                    user_id=user_id,
                    username=username,
                    normalized_username=normalized_username,
                    display_name=display_name,
                    password_hash=password_hash,
                    disabled=False,
                    created_at=now,
                    updated_at=now,
                    password_changed_at=now,
                )
                session.add(row)
                session.flush()
                session.add(
                    MembershipRow(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        role=role.value,
                        created_at=now,
                    )
                )
                session.flush()
                return _identity_user(session, row)
        except IntegrityError as error:
            raise ApplicationConflictError(
                "username already exists"
            ) from error

    def users(self, workspace_id: str) -> tuple[IdentityUser, ...]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(UserRow)
                .join(
                    MembershipRow,
                    MembershipRow.user_id == UserRow.user_id,
                )
                .where(MembershipRow.workspace_id == workspace_id)
                .order_by(UserRow.normalized_username)
            )
            return tuple(_identity_user(session, row) for row in rows)

    def credentials(
        self,
        normalized_username: str,
    ) -> StoredCredentials | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(UserRow).where(
                    UserRow.normalized_username == normalized_username
                )
            )
            if row is None:
                return None
            return StoredCredentials(
                user=_identity_user(session, row),
                password_hash=row.password_hash,
            )

    def replace_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        now: datetime,
    ) -> None:
        with Session(self._engine) as session, session.begin():
            row = session.get(UserRow, user_id)
            if row is None:
                raise AuthenticationError("user account does not exist")
            row.password_hash = password_hash
            row.password_changed_at = now
            row.updated_at = now
            session.execute(
                delete(WebSessionRow).where(
                    WebSessionRow.user_id == user_id
                )
            )

    def set_disabled(
        self,
        *,
        normalized_username: str,
        disabled: bool,
        now: datetime,
    ) -> IdentityUser:
        with Session(self._engine) as session, session.begin():
            row = session.scalar(
                select(UserRow).where(
                    UserRow.normalized_username == normalized_username
                )
            )
            if row is None:
                raise AuthenticationError("user account does not exist")
            if disabled and not row.disabled:
                owner_workspace_ids = tuple(
                    session.scalars(
                        select(MembershipRow.workspace_id).where(
                            MembershipRow.user_id == row.user_id,
                            MembershipRow.role
                            == MembershipRole.OWNER.value,
                        )
                    )
                )
                for workspace_id in owner_workspace_ids:
                    enabled_owner_count = session.scalar(
                        select(func.count())
                        .select_from(MembershipRow)
                        .join(
                            UserRow,
                            UserRow.user_id == MembershipRow.user_id,
                        )
                        .where(
                            MembershipRow.workspace_id == workspace_id,
                            MembershipRow.role
                            == MembershipRole.OWNER.value,
                            UserRow.disabled.is_(False),
                        )
                    )
                    if enabled_owner_count == 1:
                        raise ApplicationConflictError(
                            "the last enabled owner cannot be disabled"
                        )
            row.disabled = disabled
            row.updated_at = now
            if disabled:
                session.execute(
                    delete(WebSessionRow).where(
                        WebSessionRow.user_id == row.user_id
                    )
                )
            session.flush()
            return _identity_user(session, row)

    def has_enabled_owner(self, workspace_id: str) -> bool:
        with Session(self._engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(MembershipRow)
                .join(UserRow, UserRow.user_id == MembershipRow.user_id)
                .where(
                    MembershipRow.workspace_id == workspace_id,
                    MembershipRow.role == MembershipRole.OWNER.value,
                    UserRow.disabled.is_(False),
                )
            )
            return bool(count)

    def create_web_session(
        self,
        *,
        web_session_id: str,
        token_digest: str,
        user_id: str,
        now: datetime,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
    ) -> Principal:
        with Session(self._engine) as session, session.begin():
            row = session.get(UserRow, user_id)
            if row is None or row.disabled:
                raise AuthenticationError("user account is unavailable")
            session.add(
                WebSessionRow(
                    web_session_id=web_session_id,
                    token_digest=token_digest,
                    user_id=user_id,
                    created_at=now,
                    last_seen_at=now,
                    idle_expires_at=idle_expires_at,
                    absolute_expires_at=absolute_expires_at,
                )
            )
            session.flush()
            return _principal(session, row)

    def resolve_web_session(
        self,
        *,
        token_digest: str,
        now: datetime,
        idle_extension: timedelta,
        touch_interval: timedelta,
    ) -> Principal | None:
        with Session(self._engine) as session, session.begin():
            web_session = session.scalar(
                select(WebSessionRow).where(
                    WebSessionRow.token_digest == token_digest
                )
            )
            if web_session is None:
                return None
            user = session.get(UserRow, web_session.user_id)
            if (
                user is None
                or user.disabled
                or _aware(web_session.idle_expires_at) <= now
                or _aware(web_session.absolute_expires_at) <= now
            ):
                session.delete(web_session)
                return None
            if now - _aware(web_session.last_seen_at) >= touch_interval:
                web_session.last_seen_at = now
                web_session.idle_expires_at = min(
                    now + idle_extension,
                    _aware(web_session.absolute_expires_at),
                )
            return _principal(session, user)

    def delete_web_session(self, token_digest: str) -> None:
        with Session(self._engine) as session, session.begin():
            session.execute(
                delete(WebSessionRow).where(
                    WebSessionRow.token_digest == token_digest
                )
            )

    def prune_web_sessions(self, now: datetime) -> int:
        with Session(self._engine) as session, session.begin():
            result = session.execute(
                delete(WebSessionRow).where(
                    or_(
                        WebSessionRow.idle_expires_at <= now,
                        WebSessionRow.absolute_expires_at <= now,
                    )
                )
            )
            return int(result.rowcount or 0)
