"""Framework-independent local identity entities."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime


def _require_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is not UTC:
        raise ValueError(f"{field_name} must use UTC")
    return value


@dataclass(frozen=True, slots=True)
class User:
    """The sole local operator identity."""

    id: str
    username: str
    password_hash: str = field(repr=False)
    credential_version: int
    created_at: datetime
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_text(self.id, field_name="user id"))
        object.__setattr__(
            self,
            "username",
            _require_text(self.username, field_name="username"),
        )
        if not self.password_hash:
            raise ValueError("password hash must not be empty")
        if self.credential_version < 1:
            raise ValueError("credential version must be positive")
        _require_utc(self.created_at, field_name="created_at")

    def with_password_hash(self, password_hash: str) -> User:
        """Rotate credentials without mutating the persisted identity."""
        if not password_hash:
            raise ValueError("password hash must not be empty")
        return replace(
            self,
            password_hash=password_hash,
            credential_version=self.credential_version + 1,
        )


@dataclass(frozen=True, slots=True)
class PersonalSpace:
    """The one personal financial space owned by the local operator."""

    id: str
    owner_user_id: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_text(self.id, field_name="space id"))
        object.__setattr__(
            self,
            "owner_user_id",
            _require_text(self.owner_user_id, field_name="owner user id"),
        )
        object.__setattr__(self, "name", _require_text(self.name, field_name="space name"))
        _require_utc(self.created_at, field_name="created_at")


__all__ = ("PersonalSpace", "User")
