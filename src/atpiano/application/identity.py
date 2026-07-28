"""Framework-independent users, memberships, and web-session policy."""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from atpiano.application.errors import (
    ApplicationConflictError,
    AuthenticationError,
    AuthorizationError,
)
from atpiano.contracts.schemas import (
    GroupKind,
    GroupRole,
    MembershipRole,
    ProfileControllerRole,
)

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
MINIMUM_PASSWORD_CHARACTERS = 12
MAXIMUM_PASSWORD_BYTES = 1024
DEFAULT_IDLE_SESSION_LIFETIME = timedelta(days=7)
DEFAULT_ABSOLUTE_SESSION_LIFETIME = timedelta(days=30)
DEFAULT_SESSION_TOUCH_INTERVAL = timedelta(minutes=5)
LOCAL_OPERATOR_SESSION_LIFETIME = timedelta(minutes=5)


@dataclass(frozen=True)
class IdentityUser:
    user_id: str
    username: str
    display_name: str
    disabled: bool
    created_at: datetime
    memberships: tuple[WorkspaceMembership, ...]
    group_memberships: tuple[GroupMembership, ...]


@dataclass(frozen=True)
class StoredCredentials:
    user: IdentityUser
    password_hash: str


@dataclass(frozen=True)
class WorkspaceMembership:
    workspace_id: str
    role: MembershipRole
    created_at: datetime


@dataclass(frozen=True)
class GroupMembership:
    group_id: str
    role: GroupRole
    created_at: datetime


@dataclass(frozen=True)
class IdentityGroup:
    group_id: str
    name: str
    kind: GroupKind
    default_space_audience: str
    default_space_role: MembershipRole
    created_at: datetime
    current_user_role: GroupRole


@dataclass(frozen=True)
class IdentityProfile:
    profile_id: str
    display_name: str
    disabled: bool
    created_at: datetime
    controller_role: ProfileControllerRole | None


@dataclass(frozen=True)
class IdentityWorkspace:
    workspace_id: str
    name: str
    administrative_group_id: str | None
    home_profile_id: str | None
    created_by_user_id: str | None


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    memberships: tuple[WorkspaceMembership, ...]
    group_memberships: tuple[GroupMembership, ...]

    def membership(self, workspace_id: str) -> WorkspaceMembership:
        for membership in self.memberships:
            if membership.workspace_id == workspace_id:
                return membership
        raise AuthorizationError("workspace access is not allowed")

    def require_write(self, workspace_id: str) -> WorkspaceMembership:
        membership = self.membership(workspace_id)
        if membership.role is MembershipRole.VIEWER:
            raise AuthorizationError("workspace write access is not allowed")
        return membership

    def group_membership(self, group_id: str) -> GroupMembership:
        for membership in self.group_memberships:
            if membership.group_id == group_id:
                return membership
        raise AuthorizationError("group access is not allowed")

    def require_group_manage(self, group_id: str) -> GroupMembership:
        membership = self.group_membership(group_id)
        if membership.role is GroupRole.MEMBER:
            raise AuthorizationError("group management is not allowed")
        return membership


@dataclass(frozen=True)
class IssuedWebSession:
    token: str
    principal: Principal
    idle_expires_at: datetime
    absolute_expires_at: datetime


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify_and_update(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]: ...


class IdentityRepository(Protocol):
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
    ) -> IdentityUser: ...

    def users(self, workspace_id: str) -> tuple[IdentityUser, ...]: ...

    def groups(self, user_id: str) -> tuple[IdentityGroup, ...]: ...

    def profiles(
        self,
        *,
        workspace_id: str,
        controller_user_id: str,
    ) -> tuple[IdentityProfile, ...]: ...

    def workspace_group_id(self, workspace_id: str) -> str: ...

    def workspace(self, workspace_id: str) -> IdentityWorkspace | None: ...

    def create_profile(
        self,
        *,
        profile_id: str,
        group_id: str,
        display_name: str,
        created_by_user_id: str,
        now: datetime,
    ) -> IdentityProfile: ...

    def profile_available(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> bool: ...

    def credentials(
        self,
        normalized_username: str,
    ) -> StoredCredentials | None: ...

    def replace_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        now: datetime,
    ) -> None: ...

    def set_disabled(
        self,
        *,
        normalized_username: str,
        disabled: bool,
        now: datetime,
    ) -> IdentityUser: ...

    def has_enabled_owner(self, workspace_id: str) -> bool: ...

    def create_web_session(
        self,
        *,
        web_session_id: str,
        token_digest: str,
        user_id: str,
        now: datetime,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
    ) -> Principal: ...

    def resolve_web_session(
        self,
        *,
        token_digest: str,
        now: datetime,
        idle_extension: timedelta,
        touch_interval: timedelta,
    ) -> Principal | None: ...

    def delete_web_session(self, token_digest: str) -> None: ...

    def prune_web_sessions(self, now: datetime) -> int: ...


def normalize_username(username: str) -> str:
    candidate = username.strip()
    if not USERNAME_PATTERN.fullmatch(candidate):
        raise ValueError(
            "username must use 1-64 ASCII letters, digits, '.', '_', or '-'"
        )
    return candidate.casefold()


def validate_password(password: str) -> None:
    if len(password) < MINIMUM_PASSWORD_CHARACTERS:
        raise ValueError(
            f"password must contain at least {MINIMUM_PASSWORD_CHARACTERS} characters"
        )
    if len(password.encode("utf-8")) > MAXIMUM_PASSWORD_BYTES:
        raise ValueError("password is too large")


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _principal(user: IdentityUser) -> Principal:
    return Principal(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        memberships=user.memberships,
        group_memberships=user.group_memberships,
    )


def self_profile_id(user_id: str) -> str:
    value = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://atpiano.local/profile/{user_id}",
    )
    return f"profile:{value.hex}"


class IdentityApplicationService:
    """Basic local account policy independent of SQLAlchemy and FastAPI."""

    def __init__(
        self,
        repository: IdentityRepository,
        password_hasher: PasswordHasher,
        *,
        workspace_id: str,
        now: Callable[[], datetime] | None = None,
        idle_session_lifetime: timedelta = DEFAULT_IDLE_SESSION_LIFETIME,
        absolute_session_lifetime: timedelta = (
            DEFAULT_ABSOLUTE_SESSION_LIFETIME
        ),
        session_touch_interval: timedelta = (
            DEFAULT_SESSION_TOUCH_INTERVAL
        ),
    ) -> None:
        if idle_session_lifetime <= timedelta():
            raise ValueError("idle session lifetime must be positive")
        if absolute_session_lifetime < idle_session_lifetime:
            raise ValueError(
                "absolute session lifetime cannot be shorter than idle lifetime"
            )
        if (
            session_touch_interval <= timedelta()
            or session_touch_interval >= idle_session_lifetime
        ):
            raise ValueError(
                "session touch interval must be positive and shorter "
                "than the idle lifetime"
            )
        self._repository = repository
        self._password_hasher = password_hasher
        self.workspace_id = workspace_id
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._idle_session_lifetime = idle_session_lifetime
        self._absolute_session_lifetime = absolute_session_lifetime
        self._session_touch_interval = session_touch_interval
        self._dummy_hash = password_hasher.hash(
            secrets.token_urlsafe(32)
        )

    def create_user(
        self,
        username: str,
        password: str,
        *,
        display_name: str | None = None,
        role: MembershipRole = MembershipRole.OWNER,
    ) -> IdentityUser:
        normalized = normalize_username(username)
        canonical = username.strip()
        validate_password(password)
        display = (display_name or canonical).strip()
        if not 1 <= len(display) <= 128:
            raise ValueError("display name must contain 1-128 characters")
        now = self._now()
        return self._repository.create_user(
            user_id=f"user:{uuid.uuid4().hex}",
            username=canonical,
            normalized_username=normalized,
            display_name=display,
            password_hash=self._password_hasher.hash(password),
            workspace_id=self.workspace_id,
            role=role,
            now=now,
        )

    def list_users(self) -> tuple[IdentityUser, ...]:
        return self._repository.users(self.workspace_id)

    def list_groups(self, principal: Principal) -> tuple[IdentityGroup, ...]:
        return self._repository.groups(principal.user_id)

    def list_profiles(
        self,
        principal: Principal,
        workspace_id: str,
    ) -> tuple[IdentityProfile, ...]:
        principal.membership(workspace_id)
        return self._repository.profiles(
            workspace_id=workspace_id,
            controller_user_id=principal.user_id,
        )

    def workspace_group_id(
        self,
        principal: Principal,
        workspace_id: str,
    ) -> str:
        principal.membership(workspace_id)
        return self._repository.workspace_group_id(workspace_id)

    def workspace(
        self,
        principal: Principal,
        workspace_id: str,
    ) -> IdentityWorkspace:
        principal.membership(workspace_id)
        workspace = self._repository.workspace(workspace_id)
        if workspace is None:
            raise ApplicationConflictError("workspace is unavailable")
        return workspace

    def create_managed_profile(
        self,
        principal: Principal,
        *,
        group_id: str,
        display_name: str,
    ) -> IdentityProfile:
        principal.require_group_manage(group_id)
        normalized = display_name.strip()
        if not 1 <= len(normalized) <= 128:
            raise ValueError(
                "profile display name must contain 1-128 characters"
            )
        return self._repository.create_profile(
            profile_id=f"profile:{uuid.uuid4().hex}",
            group_id=group_id,
            display_name=normalized,
            created_by_user_id=principal.user_id,
            now=self._now(),
        )

    def require_profile(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        profile_id: str | None,
    ) -> None:
        principal.membership(workspace_id)
        if profile_id is None:
            return
        if not self._repository.profile_available(
            workspace_id=workspace_id,
            profile_id=profile_id,
        ):
            raise AuthorizationError(
                "performer profile is not available in this workspace"
            )

    def set_password(self, username: str, password: str) -> None:
        normalized = normalize_username(username)
        validate_password(password)
        credentials = self._repository.credentials(normalized)
        if credentials is None:
            raise AuthenticationError("user account does not exist")
        self._repository.replace_password(
            user_id=credentials.user.user_id,
            password_hash=self._password_hasher.hash(password),
            now=self._now(),
        )

    def set_disabled(
        self,
        username: str,
        *,
        disabled: bool,
    ) -> IdentityUser:
        return self._repository.set_disabled(
            normalized_username=normalize_username(username),
            disabled=disabled,
            now=self._now(),
        )

    def require_enabled_owner(self) -> None:
        if not self._repository.has_enabled_owner(self.workspace_id):
            raise ApplicationConflictError(
                "authentication requires at least one enabled workspace owner"
            )

    def login(self, username: str, password: str) -> IssuedWebSession:
        try:
            normalized = normalize_username(username)
        except ValueError:
            normalized = ""
        credentials = self._repository.credentials(normalized)
        password_hash = (
            credentials.password_hash
            if credentials is not None
            else self._dummy_hash
        )
        try:
            verified, updated_hash = self._password_hasher.verify_and_update(
                password,
                password_hash,
            )
        except (TypeError, ValueError):
            verified, updated_hash = False, None
        if (
            credentials is None
            or credentials.user.disabled
            or not verified
        ):
            raise AuthenticationError("username or password is incorrect")
        now = self._now()
        if updated_hash is not None:
            self._repository.replace_password(
                user_id=credentials.user.user_id,
                password_hash=updated_hash,
                now=now,
            )
        return self._issue_web_session(
            credentials.user.user_id,
            now=now,
            idle_expires_at=now + self._idle_session_lifetime,
            absolute_expires_at=now + self._absolute_session_lifetime,
        )

    def issue_local_operator_session(
        self,
        username: str | None = None,
    ) -> IssuedWebSession:
        """Issue a bounded session to a caller with local catalog authority."""

        normalized = (
            normalize_username(username)
            if username is not None
            else None
        )
        candidates = tuple(
            user
            for user in self.list_users()
            if (
                not user.disabled
                and any(
                    membership.workspace_id == self.workspace_id
                    for membership in user.memberships
                )
                and (
                    normalized is not None
                    or any(
                        membership.workspace_id == self.workspace_id
                        and membership.role is MembershipRole.OWNER
                        for membership in user.memberships
                    )
                )
            )
        )
        selected = next(
            (
                user
                for user in candidates
                if (
                    normalized is None
                    or normalize_username(user.username) == normalized
                )
            ),
            None,
        )
        if selected is None:
            raise ApplicationConflictError(
                "no enabled local operator account is available"
            )
        token = secrets.token_urlsafe(32)
        now = self._now()
        expires_at = now + LOCAL_OPERATOR_SESSION_LIFETIME
        return self._issue_web_session(
            selected.user_id,
            now=now,
            idle_expires_at=expires_at,
            absolute_expires_at=expires_at,
            token=token,
        )

    def _issue_web_session(
        self,
        user_id: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
        token: str | None = None,
    ) -> IssuedWebSession:
        issued_token = token or secrets.token_urlsafe(32)
        principal = self._repository.create_web_session(
            web_session_id=f"web-session:{uuid.uuid4().hex}",
            token_digest=_token_digest(issued_token),
            user_id=user_id,
            now=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        return IssuedWebSession(
            token=issued_token,
            principal=principal,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )

    def authenticate(self, token: str | None) -> Principal:
        if token is None:
            raise AuthenticationError("authentication is required")
        try:
            digest = _token_digest(token)
        except (UnicodeEncodeError, ValueError):
            raise AuthenticationError(
                "authentication is required"
            ) from None
        principal = self._repository.resolve_web_session(
            token_digest=digest,
            now=self._now(),
            idle_extension=self._idle_session_lifetime,
            touch_interval=self._session_touch_interval,
        )
        if principal is None:
            raise AuthenticationError("authentication is required")
        return principal

    def logout(self, token: str | None) -> None:
        if token is None:
            return
        try:
            digest = _token_digest(token)
        except (UnicodeEncodeError, ValueError):
            return
        self._repository.delete_web_session(digest)

    def prune_sessions(self) -> int:
        return self._repository.prune_web_sessions(self._now())
