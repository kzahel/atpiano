from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from atpiano.adapters.passwords import Argon2PasswordHasher
from atpiano.adapters.sqlite_identity import SqlAlchemyIdentityRepository
from atpiano.application.errors import (
    ApplicationConflictError,
    AuthenticationError,
    AuthorizationError,
)
from atpiano.application.identity import IdentityApplicationService
from atpiano.contracts.schemas import MembershipRole
from atpiano.persistence import initialize_catalog


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
