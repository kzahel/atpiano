"""Administrator-only local user commands."""

from __future__ import annotations

import getpass
from pathlib import Path

from atpiano.adapters.passwords import Argon2PasswordHasher
from atpiano.adapters.sqlite_identity import SqlAlchemyIdentityRepository
from atpiano.application.identity import IdentityApplicationService
from atpiano.contracts.schemas import MembershipRole
from atpiano.persistence import initialize_catalog


def identity_service(
    workspace_directory: Path,
) -> tuple[IdentityApplicationService, object]:
    _, engine = initialize_catalog(workspace_directory)
    service = IdentityApplicationService(
        SqlAlchemyIdentityRepository(engine),
        Argon2PasswordHasher(),
        workspace_id="local",
    )
    return service, engine


def prompt_password(*, confirm: bool) -> str:
    password = getpass.getpass("Password: ")
    if confirm:
        repeated = getpass.getpass("Confirm password: ")
        if password != repeated:
            raise ValueError("password confirmation does not match")
    return password


def run_users_command(args: object) -> int:
    workspace = Path(getattr(args, "workspace"))
    service, engine = identity_service(workspace)
    try:
        command = str(getattr(args, "users_command"))
        username = getattr(args, "username", None)
        if command == "create":
            user = service.create_user(
                str(username),
                prompt_password(confirm=True),
                display_name=getattr(args, "display_name"),
                role=MembershipRole(str(getattr(args, "role"))),
            )
            role = user.memberships[0].role.value
            print(f"created {user.username} ({role})")
            return 0
        if command == "set-password":
            service.set_password(
                str(username),
                prompt_password(confirm=True),
            )
            print(f"updated password for {username}")
            return 0
        if command == "disable":
            user = service.set_disabled(str(username), disabled=True)
            print(f"disabled {user.username}")
            return 0
        if command == "enable":
            user = service.set_disabled(str(username), disabled=False)
            print(f"enabled {user.username}")
            return 0
        if command == "list":
            for user in service.list_users():
                membership = user.memberships[0]
                state = "disabled" if user.disabled else "enabled"
                print(
                    f"{user.username}\t{membership.role.value}\t"
                    f"{state}\t{user.display_name}"
                )
            return 0
        raise ValueError("a users subcommand is required")
    finally:
        engine.dispose()
