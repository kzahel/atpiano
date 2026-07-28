"""Argon2 password hashing adapter."""

from __future__ import annotations

from pwdlib import PasswordHash


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify_and_update(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]:
        return self._password_hash.verify_and_update(
            password,
            password_hash,
        )
