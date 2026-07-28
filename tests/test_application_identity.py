from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from atpiano.adapters.passwords import Argon2PasswordHasher
from atpiano.adapters.sqlite_identity import SqlAlchemyIdentityRepository
from atpiano.application.errors import (
    ApplicationConflictError,
    AuthenticationError,
    AuthorizationError,
)
from atpiano.application.identity import IdentityApplicationService
from atpiano.contracts.schemas import GroupRole, MembershipRole
from atpiano.persistence import initialize_catalog
from atpiano.persistence.catalog import HOME_GROUP_ID
from atpiano.persistence.models import (
    WorkspaceGroupGrantRow,
    WorkspaceRow,
)


def _service(
    tmp_path: Path,
    *,
    now: list[datetime] | None = None,
) -> tuple[IdentityApplicationService, object]:
    _, engine = initialize_catalog(tmp_path)
    clock = now or [datetime(2026, 7, 28, tzinfo=timezone.utc)]
    return (
        IdentityApplicationService(
            SqlAlchemyIdentityRepository(engine),
            Argon2PasswordHasher(),
            workspace_id="local",
            now=lambda: clock[0],
            idle_session_lifetime=timedelta(hours=1),
            absolute_session_lifetime=timedelta(hours=8),
        ),
        engine,
    )


def test_user_login_membership_and_logout(tmp_path: Path) -> None:
    service, engine = _service(tmp_path)
    try:
        user = service.create_user(
            "Alice",
            "correct horse battery staple",
            display_name="Alice G.",
        )
        service.require_enabled_owner()
        issued = service.login(
            "alice",
            "correct horse battery staple",
        )

        assert user.username == "Alice"
        assert issued.principal.user_id == user.user_id
        assert issued.principal.membership("local").role is MembershipRole.OWNER
        assert issued.principal.require_write("local").role is MembershipRole.OWNER
        assert service.authenticate(issued.token) == issued.principal

        service.logout(issued.token)
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.token)
    finally:
        engine.dispose()


def test_login_failure_is_generic_and_viewer_is_read_only(
    tmp_path: Path,
) -> None:
    service, engine = _service(tmp_path)
    try:
        service.create_user(
            "viewer",
            "a sufficiently long viewer password",
            role=MembershipRole.VIEWER,
        )
        for username, password in (
            ("missing", "a sufficiently long viewer password"),
            ("viewer", "the password is incorrect"),
        ):
            with pytest.raises(
                AuthenticationError,
                match="username or password is incorrect",
            ):
                service.login(username, password)
        principal = service.login(
            "viewer",
            "a sufficiently long viewer password",
        ).principal
        with pytest.raises(AuthorizationError):
            principal.require_write("local")
    finally:
        engine.dispose()


def test_password_change_and_disable_revoke_sessions(
    tmp_path: Path,
) -> None:
    service, engine = _service(tmp_path)
    try:
        service.create_user("owner", "the first long owner password")
        service.create_user("other", "the other long owner password")
        first = service.login(
            "owner",
            "the first long owner password",
        )
        service.set_password("owner", "a changed long owner password")
        with pytest.raises(AuthenticationError):
            service.authenticate(first.token)
        second = service.login("owner", "a changed long owner password")
        service.set_disabled("owner", disabled=True)
        with pytest.raises(AuthenticationError):
            service.authenticate(second.token)
        with pytest.raises(AuthenticationError):
            service.login("owner", "a changed long owner password")
    finally:
        engine.dispose()


def test_last_enabled_owner_cannot_be_disabled(tmp_path: Path) -> None:
    service, engine = _service(tmp_path)
    try:
        service.create_user("owner", "the only long owner password")
        with pytest.raises(
            ApplicationConflictError,
            match="last enabled owner",
        ):
            service.set_disabled("owner", disabled=True)
    finally:
        engine.dispose()


def test_idle_and_absolute_session_expiry(tmp_path: Path) -> None:
    clock = [datetime(2026, 7, 28, tzinfo=timezone.utc)]
    service, engine = _service(tmp_path, now=clock)
    try:
        service.create_user("owner", "the only long owner password")
        issued = service.login("owner", "the only long owner password")
        clock[0] += timedelta(minutes=50)
        assert service.authenticate(issued.token).username == "owner"
        clock[0] += timedelta(minutes=61)
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.token)
    finally:
        engine.dispose()


def test_local_operator_session_is_bounded_and_revocable(
    tmp_path: Path,
) -> None:
    clock = [datetime(2026, 7, 28, tzinfo=timezone.utc)]
    service, engine = _service(tmp_path, now=clock)
    try:
        service.create_user("owner", "the only long owner password")
        issued = service.issue_local_operator_session()

        assert issued.principal.username == "owner"
        assert issued.absolute_expires_at == clock[0] + timedelta(minutes=5)
        assert service.authenticate(issued.token) == issued.principal

        service.logout(issued.token)
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.token)
    finally:
        engine.dispose()


def test_username_and_password_policy(tmp_path: Path) -> None:
    service, engine = _service(tmp_path)
    try:
        with pytest.raises(ValueError, match="username"):
            service.create_user("not allowed!", "a sufficiently long password")
        with pytest.raises(ValueError, match="at least"):
            service.create_user("valid", "too short")
        service.create_user("CaseName", "a sufficiently long password")
        with pytest.raises(ApplicationConflictError, match="already exists"):
            service.create_user(
                "casename",
                "another sufficiently long password",
            )
    finally:
        engine.dispose()


def test_group_profiles_separate_performer_from_login_account(
    tmp_path: Path,
) -> None:
    service, engine = _service(tmp_path)
    try:
        owner = service.create_user(
            "owner",
            "the owner has a sufficiently long password",
            display_name="Kyle",
        )
        viewer = service.create_user(
            "brother",
            "the brother has a sufficiently long password",
            display_name="Brother",
            role=MembershipRole.VIEWER,
        )
        owner_principal = service.login(
            "owner",
            "the owner has a sufficiently long password",
        ).principal
        brother_principal = service.login(
            "brother",
            "the brother has a sufficiently long password",
        ).principal

        groups = service.list_groups(owner_principal)
        assert len(groups) == 1
        assert groups[0].current_user_role is GroupRole.OWNER
        assert brother_principal.group_membership(
            groups[0].group_id
        ).role is GroupRole.MEMBER

        child = service.create_managed_profile(
            owner_principal,
            group_id=groups[0].group_id,
            display_name="Daughter",
        )
        profiles = service.list_profiles(owner_principal, "local")
        assert {profile.display_name for profile in profiles} == {
            "Brother",
            "Daughter",
            "Kyle",
        }
        brother_profiles = service.list_profiles(
            brother_principal,
            "local",
        )
        assert {
            profile.display_name for profile in brother_profiles
        } == {"Brother", "Daughter", "Kyle"}
        assert next(
            profile
            for profile in brother_profiles
            if profile.display_name == "Brother"
        ).controller_role is not None
        service.require_profile(
            brother_principal,
            workspace_id="local",
            profile_id=child.profile_id,
        )
        with pytest.raises(AuthorizationError, match="management"):
            service.create_managed_profile(
                brother_principal,
                group_id=groups[0].group_id,
                display_name="Nephew",
            )
        assert owner.group_memberships
        assert viewer.group_memberships
    finally:
        engine.dispose()


def test_group_workspace_grant_is_explicit_and_does_not_leak(
    tmp_path: Path,
) -> None:
    service, engine = _service(tmp_path)
    try:
        owner = service.create_user(
            "owner",
            "the owner has a sufficiently long password",
        )
        service.create_user(
            "brother",
            "the brother has a sufficiently long password",
            role=MembershipRole.VIEWER,
        )
        now = datetime(2026, 7, 28, tzinfo=timezone.utc)
        with Session(engine) as session, session.begin():
            for workspace_id in ("shared", "private"):
                session.add(
                    WorkspaceRow(
                        workspace_id=workspace_id,
                        name=workspace_id.title(),
                        mode="local",
                        created_at=now,
                        administrative_group_id=HOME_GROUP_ID,
                        home_profile_id=None,
                        storage_key=f"test:{workspace_id}",
                        created_by_user_id=owner.user_id,
                        updated_at=now,
                        archived_at=None,
                    )
                )
            session.flush()
            session.add(
                WorkspaceGroupGrantRow(
                    workspace_id="shared",
                    group_id=HOME_GROUP_ID,
                    role=MembershipRole.EDITOR.value,
                    granted_by_user_id=owner.user_id,
                    created_at=now,
                )
            )

        principal = service.login(
            "brother",
            "the brother has a sufficiently long password",
        ).principal
        assert principal.membership(
            "shared"
        ).role is MembershipRole.EDITOR
        with pytest.raises(AuthorizationError, match="not allowed"):
            principal.membership("private")
    finally:
        engine.dispose()
