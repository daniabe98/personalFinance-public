"""Argon2id password hashing adapter."""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2PasswordHasher:
    """Hash credentials with the library's current Argon2id profile."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Type.ID)

    def hash(self, password: str) -> str:
        """Return an Argon2id encoded hash and never retain the password."""
        if not password:
            raise ValueError("password must not be empty")
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Verify without propagating malformed-hash or mismatch distinctions."""
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False


__all__ = ("Argon2PasswordHasher",)
