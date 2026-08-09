"""Local identity use cases and inward-facing collaborator contracts."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.identity.domain.user import PersonalSpace, User


class BootstrapAlreadyCompletedError(RuntimeError):
    """Raised when the one local identity has already been established."""


class BootstrapRequiredError(RuntimeError):
    """Raised when a local-only operation requires prior bootstrap."""


class AuthenticationFailedError(RuntimeError):
    """A deliberately generic credential failure."""

    def __init__(self) -> None:
        super().__init__("invalid credentials")


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Minimal immutable identity data safe to inject into use cases."""

    user_id: str
    space_id: str
    username: str


@dataclass(frozen=True, slots=True)
class SessionGrant:
    """One-time bearer material returned only at session creation."""

    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    expires_at: datetime
    principal_user_id: str
    principal_space_id: str

    def __post_init__(self) -> None:
        if self.expires_at.tzinfo is not UTC:
            raise ValueError("session expiry must use UTC")


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class IdentityRepository(Protocol):
    def has_any_user(self) -> bool: ...

    def add_user(self, user: User) -> None: ...

    def add_space(self, space: PersonalSpace) -> None: ...

    def user_by_username(self, username: str) -> User | None: ...

    def only_user(self) -> User | None: ...

    def space_for_user(self, user_id: str) -> PersonalSpace | None: ...

    def update_user(self, user: User) -> None: ...

    def revoke_sessions(self, user_id: str, revoked_at: datetime) -> None: ...


class IdentityTransaction(AbstractContextManager["IdentityTransaction"], Protocol):
    @property
    def identity(self) -> IdentityRepository: ...

    def commit(self) -> None: ...


class SessionGateway(Protocol):
    def create(
        self,
        *,
        user_id: str,
        space_id: str,
        now: datetime,
    ) -> SessionGrant: ...

    def revoke(self, session_token: str, revoked_at: datetime) -> bool: ...


class AuthenticationAuditSink(Protocol):
    """Producer-owned shape implemented by the durable audit binding."""

    def record_authentication(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None: ...


class IdentityService:
    """Coordinate one local identity, credentials and opaque sessions."""

    def __init__(
        self,
        *,
        transaction_factory: Callable[[], IdentityTransaction],
        password_hasher: PasswordHasher,
        sessions: SessionGateway,
        audit_sink: AuthenticationAuditSink,
        clock: Callable[[], datetime],
    ) -> None:
        self._transaction_factory = transaction_factory
        self._password_hasher = password_hasher
        self._sessions = sessions
        self._audit_sink = audit_sink
        self._clock = clock
        self._dummy_password_hash = password_hasher.hash("dummy credential comparison")

    def bootstrap(
        self,
        *,
        username: str,
        password: str,
        space_name: str,
    ) -> AuthenticatedPrincipal:
        """Atomically create the only user and personal financial space."""
        now = self._utc_now()
        user = User(
            id=str(uuid4()),
            username=username,
            password_hash=self._password_hasher.hash(password),
            credential_version=1,
            created_at=now,
        )
        space = PersonalSpace(
            id=str(uuid4()),
            owner_user_id=user.id,
            name=space_name,
            created_at=now,
        )
        with self._transaction_factory() as transaction:
            if transaction.identity.has_any_user():
                raise BootstrapAlreadyCompletedError("local identity is already configured")
            transaction.identity.add_user(user)
            transaction.identity.add_space(space)
            transaction.commit()
        return self._principal(user, space)

    def login(
        self,
        *,
        username: str,
        password: str,
        correlation_id: str,
    ) -> SessionGrant:
        """Authenticate without disclosing which credential was invalid."""
        with self._transaction_factory() as transaction:
            user = transaction.identity.user_by_username(username)
            candidate_hash = user.password_hash if user is not None else self._dummy_password_hash
            password_matches = self._password_hasher.verify(password, candidate_hash)
            space = (
                transaction.identity.space_for_user(user.id)
                if user is not None and password_matches and user.active
                else None
            )
        if user is None or not password_matches or not user.active or space is None:
            self._audit(
                action="LOGIN",
                result="FAILURE",
                actor_id=None,
                space_id=None,
                correlation_id=correlation_id,
            )
            raise AuthenticationFailedError
        grant = self._sessions.create(user_id=user.id, space_id=space.id, now=self._utc_now())
        self._audit(
            action="LOGIN",
            result="SUCCESS",
            actor_id=user.id,
            space_id=space.id,
            correlation_id=correlation_id,
        )
        return grant

    def logout(
        self,
        *,
        session_token: str,
        principal_user_id: str,
        principal_space_id: str,
        correlation_id: str,
    ) -> None:
        """Revoke one bearer session and record only its trusted identity."""
        self._sessions.revoke(session_token, self._utc_now())
        self._audit(
            action="LOGOUT",
            result="SUCCESS",
            actor_id=principal_user_id,
            space_id=principal_space_id,
            correlation_id=correlation_id,
        )

    def reset_credentials(
        self,
        *,
        new_password: str,
        correlation_id: str,
    ) -> None:
        """Rotate the sole credential and revoke all prior sessions atomically."""
        now = self._utc_now()
        with self._transaction_factory() as transaction:
            user = transaction.identity.only_user()
            if user is None:
                raise BootstrapRequiredError("local identity has not been configured")
            space = transaction.identity.space_for_user(user.id)
            if space is None:
                raise BootstrapRequiredError("personal space is unavailable")
            transaction.identity.update_user(
                user.with_password_hash(self._password_hasher.hash(new_password))
            )
            transaction.identity.revoke_sessions(user.id, now)
            transaction.commit()
        self._audit(
            action="CREDENTIAL_RESET",
            result="SUCCESS",
            actor_id=user.id,
            space_id=space.id,
            correlation_id=correlation_id,
        )

    def _utc_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware value")
        return now.astimezone(UTC)

    def _audit(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None:
        self._audit_sink.record_authentication(
            action=action,
            result=result,
            actor_id=actor_id,
            space_id=space_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _principal(user: User, space: PersonalSpace) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            user_id=user.id,
            space_id=space.id,
            username=user.username,
        )


__all__ = (
    "AuthenticatedPrincipal",
    "AuthenticationFailedError",
    "BootstrapAlreadyCompletedError",
    "BootstrapRequiredError",
    "IdentityService",
    "SessionGrant",
)
