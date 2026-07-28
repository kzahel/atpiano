from __future__ import annotations

from pathlib import Path

from atpiano.cli import build_parser, main


def test_users_parser_has_basic_account_commands(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "users",
            "--workspace",
            str(tmp_path),
            "create",
            "alice",
            "--role",
            "viewer",
        ]
    )

    assert args.command == "users"
    assert args.users_command == "create"
    assert args.role == "viewer"


def test_users_cli_creates_lists_and_changes_password(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    passwords = iter(
        [
            "the initial long password",
            "the initial long password",
            "the replacement long password",
            "the replacement long password",
        ]
    )
    monkeypatch.setattr(
        "getpass.getpass",
        lambda _prompt: next(passwords),
    )

    prefix = ["users", "--workspace", str(tmp_path)]
    assert main([*prefix, "create", "alice"]) == 0
    assert main([*prefix, "list"]) == 0
    assert main([*prefix, "set-password", "alice"]) == 0

    output = capsys.readouterr().out
    assert "created alice (owner)" in output
    assert "alice\towner\tenabled\talice" in output
    assert "updated password for alice" in output
    assert "the initial long password" not in output
