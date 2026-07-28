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
    GroupMembership,
    IdentityGroup,
    IdentityProfile,
    IdentityUser,
    IdentityWorkspace,
    Principal,
    StoredCredentials,
    WorkspaceMembership,
    self_profile_id,
)
from atpiano.contracts.schemas import (
    GroupKind,
    GroupRole,
    MembershipRole,
    ProfileControllerRole,
)
from atpiano.persistence.models import (
    GroupMembershipRow,
    GroupProfileRow,
    GroupRow,
    MembershipRow,
    ProfileControllerRow,
    ProfileRow,
    UserRow,
    WebSessionRow,
    WorkspaceGroupGrantRow,
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
    roles: dict[str, tuple[MembershipRole, datetime]] = {}
    direct_rows = session.scalars(
        select(MembershipRow)
        .where(MembershipRow.user_id == user_id)
        .order_by(MembershipRow.workspace_id)
    )
    strength = {
        MembershipRole.VIEWER: 1,
        MembershipRole.EDITOR: 2,
        MembershipRole.OWNER: 3,
    }
    for row in direct_rows:
        roles[row.workspace_id] = (
            MembershipRole(row.role),
            _aware(row.created_at),
        )
    grant_rows = session.execute(
        select(
            WorkspaceGroupGrantRow.workspace_id,
            WorkspaceGroupGrantRow.role,
            WorkspaceGroupGrantRow.created_at,
        )
        .join(
            GroupMembershipRow,
            GroupMembershipRow.group_id
            == WorkspaceGroupGrantRow.group_id,
        )
        .where(GroupMembershipRow.user_id == user_id)
    )
    for workspace_id, role_value, created_at in grant_rows:
        role = MembershipRole(role_value)
        current = roles.get(workspace_id)
        if current is None or strength[role] > strength[current[0]]:
            roles[workspace_id] = (role, _aware(created_at))
    return tuple(
        WorkspaceMembership(
            workspace_id=workspace_id,
            role=role,
            created_at=created_at,
        )
        for workspace_id, (role, created_at) in sorted(roles.items())
    )


def _group_memberships(
    session: Session,
    user_id: str,
) -> tuple[GroupMembership, ...]:
    rows = session.scalars(
        select(GroupMembershipRow)
        .where(GroupMembershipRow.user_id == user_id)
        .order_by(GroupMembershipRow.group_id)
    )
    return tuple(
        GroupMembership(
            group_id=row.group_id,
            role=GroupRole(row.role),
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
        group_memberships=_group_memberships(session, row.user_id),
    )


def _principal(session: Session, row: UserRow) -> Principal:
    user = _identity_user(session, row)
    return Principal(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        memberships=user.memberships,
        group_memberships=user.group_memberships,
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
                workspace = session.get(WorkspaceRow, workspace_id)
                if (
                    workspace is None
                    or workspace.administrative_group_id is None
                ):
                    raise ApplicationConflictError(
                        "workspace group is unavailable"
                    )
                group_id = workspace.administrative_group_id
                session.add(
                    GroupMembershipRow(
                        group_id=group_id,
                        user_id=user_id,
                        role=(
                            GroupRole.OWNER.value
                            if role is MembershipRole.OWNER
                            else GroupRole.MEMBER.value
                        ),
                        created_at=now,
                    )
                )
                profile_id = self_profile_id(user_id)
                session.add(
                    ProfileRow(
                        profile_id=profile_id,
                        display_name=display_name,
                        created_by_user_id=user_id,
                        disabled=False,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.flush()
                session.add(
                    ProfileControllerRow(
                        profile_id=profile_id,
                        user_id=user_id,
                        role=ProfileControllerRole.OWNER.value,
                        created_at=now,
                    )
                )
                session.add(
                    GroupProfileRow(
                        group_id=group_id,
                        profile_id=profile_id,
                        created_at=now,
                    )
                )
                group = session.get(GroupRow, group_id)
                if group is not None and group.created_by_user_id is None:
                    group.created_by_user_id = user_id
                    group.updated_at = now
                workspace = session.get(WorkspaceRow, workspace_id)
                if (
                    workspace is not None
                    and workspace.home_profile_id is None
                    and role is MembershipRole.OWNER
                ):
                    workspace.home_profile_id = profile_id
                    workspace.updated_at = now
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

    def groups(self, user_id: str) -> tuple[IdentityGroup, ...]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(GroupRow, GroupMembershipRow)
                .join(
                    GroupMembershipRow,
                    GroupMembershipRow.group_id == GroupRow.group_id,
                )
                .where(
                    GroupMembershipRow.user_id == user_id,
                    GroupRow.archived_at.is_(None),
                )
                .order_by(GroupRow.name, GroupRow.group_id)
            )
            return tuple(
                IdentityGroup(
                    group_id=group.group_id,
                    name=group.name,
                    kind=GroupKind(group.kind),
                    default_space_audience=group.default_space_audience,
                    default_space_role=MembershipRole(
                        group.default_space_role
                    ),
                    created_at=_aware(group.created_at),
                    current_user_role=GroupRole(membership.role),
                )
                for group, membership in rows
            )

    def profiles(
        self,
        *,
        workspace_id: str,
        controller_user_id: str,
    ) -> tuple[IdentityProfile, ...]:
        with Session(self._engine) as session:
            workspace = session.get(WorkspaceRow, workspace_id)
            if (
                workspace is None
                or workspace.administrative_group_id is None
            ):
                raise ApplicationConflictError(
                    "workspace group is unavailable"
                )
            rows = session.scalars(
                select(ProfileRow)
                .join(
                    GroupProfileRow,
                    GroupProfileRow.profile_id == ProfileRow.profile_id,
                )
                .where(
                    GroupProfileRow.group_id
                    == workspace.administrative_group_id,
                )
                .order_by(ProfileRow.display_name, ProfileRow.profile_id)
            )
            profiles: list[IdentityProfile] = []
            for row in rows:
                controller = session.get(
                    ProfileControllerRow,
                    (row.profile_id, controller_user_id),
                )
                profiles.append(
                    IdentityProfile(
                        profile_id=row.profile_id,
                        display_name=row.display_name,
                        disabled=row.disabled,
                        created_at=_aware(row.created_at),
                        controller_role=(
                            ProfileControllerRole(controller.role)
                            if controller is not None
                            else None
                        ),
                    )
                )
            return tuple(profiles)

    def workspace_group_id(self, workspace_id: str) -> str:
        with Session(self._engine) as session:
            workspace = session.get(WorkspaceRow, workspace_id)
            if (
                workspace is None
                or workspace.administrative_group_id is None
            ):
                raise ApplicationConflictError(
                    "workspace group is unavailable"
                )
            return workspace.administrative_group_id

    def workspace(self, workspace_id: str) -> IdentityWorkspace | None:
        with Session(self._engine) as session:
            workspace = session.get(WorkspaceRow, workspace_id)
            if workspace is None:
                return None
            return IdentityWorkspace(
                workspace_id=workspace.workspace_id,
                name=workspace.name,
                administrative_group_id=(
                    workspace.administrative_group_id
                ),
                home_profile_id=workspace.home_profile_id,
                created_by_user_id=workspace.created_by_user_id,
            )

    def create_profile(
        self,
        *,
        profile_id: str,
        group_id: str,
        display_name: str,
        created_by_user_id: str,
        now: datetime,
    ) -> IdentityProfile:
        try:
            with Session(self._engine) as session, session.begin():
                if session.get(GroupRow, group_id) is None:
                    raise ApplicationConflictError("group does not exist")
                row = ProfileRow(
                    profile_id=profile_id,
                    display_name=display_name,
                    created_by_user_id=created_by_user_id,
                    disabled=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                session.add(
                    ProfileControllerRow(
                        profile_id=profile_id,
                        user_id=created_by_user_id,
                        role=ProfileControllerRole.OWNER.value,
                        created_at=now,
                    )
                )
                session.add(
                    GroupProfileRow(
                        group_id=group_id,
                        profile_id=profile_id,
                        created_at=now,
                    )
                )
                session.flush()
                return IdentityProfile(
                    profile_id=row.profile_id,
                    display_name=row.display_name,
                    disabled=row.disabled,
                    created_at=_aware(row.created_at),
                    controller_role=ProfileControllerRole.OWNER,
                )
        except IntegrityError as error:
            raise ApplicationConflictError(
                "profile could not be created"
            ) from error

    def profile_available(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> bool:
        with Session(self._engine) as session:
            workspace = session.get(WorkspaceRow, workspace_id)
            if (
                workspace is None
                or workspace.administrative_group_id is None
            ):
                return False
            count = session.scalar(
                select(func.count())
                .select_from(ProfileRow)
                .join(
                    GroupProfileRow,
                    GroupProfileRow.profile_id == ProfileRow.profile_id,
                )
                .where(
                    ProfileRow.profile_id == profile_id,
                    ProfileRow.disabled.is_(False),
                    GroupProfileRow.group_id
                    == workspace.administrative_group_id,
                )
            )
            return bool(count)

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
