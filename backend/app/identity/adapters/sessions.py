"""SQLAlchemy identity persistence and opaque server-side sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.identity.adapters.passwords import Argon2PasswordHasher
from app.identity.application.service import (
    AuthenticatedPrincipal,
    AuthenticationAuditSink,
    IdentityRepository,
    IdentityService,
    IdentityTransaction,
    SessionGrant,
)
from app.identity.domain.user import PersonalSpace, User
from app.shared.config import Settings, get_settings
from app.shared.database import SessionFactory, create_engine, create_session_factory
from app.shared.models_identity import SessionRecord, SpaceRecord, UserRecord
from app.shared.unit_of_work import SqlAlchemyUnitOfWork, UnitOfWorkFactory

SESSION_TOKEN_BYTES = 32
DEFAULT_SESSION_LIFETIME = timedelta(hours=12)
CSRF_TOKEN_CONTEXT = b"personal-finance:csrf:v1"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _csrf_token(session_token: str) -> str:
    """Derive a session-bound token that can be returned without rotating state."""
    return hmac.new(
        session_token.encode("utf-8"),
        CSRF_TOKEN_CONTEXT,
        hashlib.sha256,
    ).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class _SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def has_any_user(self) -> bool:
        return self._session.scalar(select(UserRecord.id).limit(1)) is not None

    def add_user(self, user: User) -> None:
        self._session.add(
            UserRecord(
                id=user.id,
                username=user.username,
                password_hash=user.password_hash,
                credential_version=user.credential_version,
                created_at=user.created_at,
            )
        )
        self._session.flush()

    def add_space(self, space: PersonalSpace) -> None:
        self._session.add(
            SpaceRecord(
                id=space.id,
                owner_user_id=space.owner_user_id,
                name=space.name,
                created_at=space.created_at,
            )
        )

    def user_by_username(self, username: str) -> User | None:
        record = self._session.scalar(select(UserRecord).where(UserRecord.username == username))
        return self._to_user(record) if record is not None else None

    def only_user(self) -> User | None:
        records = tuple(self._session.scalars(select(UserRecord).limit(2)))
        if len(records) > 1:
            raise RuntimeError("multiple local identities violate the bootstrap invariant")
        return self._to_user(records[0]) if records else None

    def space_for_user(self, user_id: str) -> PersonalSpace | None:
        record = self._session.scalar(
            select(SpaceRecord).where(SpaceRecord.owner_user_id == user_id)
        )
        return self._to_space(record) if record is not None else None

    def update_user(self, user: User) -> None:
        record = self._session.get(UserRecord, user.id)
        if record is None:
            raise RuntimeError("local identity disappeared during credential reset")
        record.password_hash = user.password_hash
        record.credential_version = user.credential_version

    def revoke_sessions(self, user_id: str, revoked_at: datetime) -> None:
        self._session.execute(
            update(SessionRecord)
            .where(
                SessionRecord.user_id == user_id,
                SessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    @staticmethod
    def _to_user(record: UserRecord) -> User:
        return User(
            id=record.id,
            username=record.username,
            password_hash=record.password_hash,
            credential_version=record.credential_version,
            created_at=_as_utc(record.created_at),
        )

    @staticmethod
    def _to_space(record: SpaceRecord) -> PersonalSpace:
        return PersonalSpace(
            id=record.id,
            owner_user_id=record.owner_user_id,
            name=record.name,
            created_at=_as_utc(record.created_at),
        )


class _SqlAlchemyIdentityTransaction(IdentityTransaction):
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._unit_of_work = unit_of_work
        self._identity: _SqlAlchemyIdentityRepository | None = None

    @property
    def identity(self) -> IdentityRepository:
        if self._identity is None:
            raise RuntimeError("identity transaction has not been entered")
        return self._identity

    def __enter__(self) -> _SqlAlchemyIdentityTransaction:
        self._unit_of_work.__enter__()
        self._identity = _SqlAlchemyIdentityRepository(self._unit_of_work.session)
        return self

    def commit(self) -> None:
        self._unit_of_work.commit()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self._identity = None
        return self._unit_of_work.__exit__(exception_type, exception, traceback)


class SqlAlchemyIdentityTransactionFactory:
    """Bind the framework-independent identity transaction to the shared UoW."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._unit_of_work_factory = UnitOfWorkFactory(session_factory)

    def __call__(self) -> IdentityTransaction:
        return _SqlAlchemyIdentityTransaction(self._unit_of_work_factory())


class OpaqueSessionManager:
    """Generate bearer values once and persist only their SHA-256 digests."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        lifetime: timedelta = DEFAULT_SESSION_LIFETIME,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if lifetime <= timedelta(0):
            raise ValueError("session lifetime must be positive")
        self._session_factory = session_factory
        self._lifetime = lifetime
        self._clock = clock

    def create(
        self,
        *,
        user_id: str,
        space_id: str,
        now: datetime,
    ) -> SessionGrant:
        """Create an opaque session while retaining only fixed-length digests."""
        issued_at = _as_utc(now)
        expires_at = issued_at + self._lifetime
        space = self._space_for_user(user_id)
        if space is None or not hmac.compare_digest(space.id, space_id):
            raise RuntimeError("session principal does not own the personal space")
        session_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        csrf_token = _csrf_token(session_token)
        with self._session_factory() as database, database.begin():
            database.add(
                SessionRecord(
                    id=str(uuid4()),
                    user_id=user_id,
                    token_hash=_digest(session_token),
                    csrf_token_hash=_digest(csrf_token),
                    expires_at=expires_at,
                    created_at=issued_at,
                    revoked_at=None,
                )
            )
        return SessionGrant(
            session_token=session_token,
            csrf_token=csrf_token,
            expires_at=expires_at,
            principal_user_id=user_id,
            principal_space_id=space.id,
        )

    def authenticate(
        self,
        session_token: str,
        *,
        at: datetime | None = None,
    ) -> AuthenticatedPrincipal | None:
        """Resolve one active digest into the minimal immutable principal."""
        if not session_token:
            return None
        checked_at = _as_utc(at or self._clock())
        with self._session_factory() as database:
            row = database.execute(
                select(SessionRecord, UserRecord, SpaceRecord)
                .join(UserRecord, SessionRecord.user_id == UserRecord.id)
                .join(SpaceRecord, SpaceRecord.owner_user_id == UserRecord.id)
                .where(SessionRecord.token_hash == _digest(session_token))
            ).one_or_none()
        if row is None:
            return None
        session, user, space = row
        if session.revoked_at is not None or checked_at >= _as_utc(session.expires_at):
            return None
        return AuthenticatedPrincipal(
            user_id=user.id,
            space_id=space.id,
            username=user.username,
        )

    def validate_csrf(self, session_token: str, csrf_token: str) -> bool:
        """Compare the active session's stored CSRF digest in constant time."""
        if not session_token or not csrf_token:
            return False
        with self._session_factory() as database:
            record = database.scalar(
                select(SessionRecord).where(SessionRecord.token_hash == _digest(session_token))
            )
        if record is None:
            return False
        if record.revoked_at is not None or _as_utc(self._clock()) >= _as_utc(record.expires_at):
            return False
        return hmac.compare_digest(record.csrf_token_hash, _digest(csrf_token))

    def csrf_for_session(self, session_token: str) -> str | None:
        """Return the stable CSRF token for one active opaque session."""
        if not session_token:
            return None
        csrf_token = _csrf_token(session_token)
        with self._session_factory() as database:
            record = database.scalar(
                select(SessionRecord).where(SessionRecord.token_hash == _digest(session_token))
            )
            if (
                record is None
                or record.revoked_at is not None
                or _as_utc(self._clock()) >= _as_utc(record.expires_at)
                or not hmac.compare_digest(record.csrf_token_hash, _digest(csrf_token))
            ):
                return None
        return csrf_token

    def revoke(self, session_token: str, revoked_at: datetime) -> bool:
        """Immediately revoke one session digest without persisting its bearer."""
        if not session_token:
            return False
        with self._session_factory() as database, database.begin():
            record = database.scalar(
                select(SessionRecord).where(SessionRecord.token_hash == _digest(session_token))
            )
            if record is None or record.revoked_at is not None:
                return False
            record.revoked_at = _as_utc(revoked_at)
        return True

    def _space_for_user(self, user_id: str) -> PersonalSpace | None:
        with self._session_factory() as database:
            record = database.scalar(
                select(SpaceRecord).where(SpaceRecord.owner_user_id == user_id)
            )
        return _SqlAlchemyIdentityRepository._to_space(record) if record is not None else None


class _FailClosedAuditSink:
    def record_authentication(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None:
        del action, result, actor_id, space_id, correlation_id
        raise RuntimeError("durable authentication audit sink is not configured")


def build_identity_service(
    *,
    settings: Settings | None = None,
    audit_sink: AuthenticationAuditSink | None = None,
) -> IdentityService:
    """Compose identity adapters; fail closed if durable audit is not injected."""
    resolved_settings = settings or get_settings()
    engine = create_engine(
        resolved_settings.database_url,
        busy_timeout_ms=resolved_settings.busy_timeout_ms,
    )
    session_factory = create_session_factory(engine)
    sessions = OpaqueSessionManager(session_factory)
    return IdentityService(
        transaction_factory=SqlAlchemyIdentityTransactionFactory(session_factory),
        password_hasher=Argon2PasswordHasher(),
        sessions=sessions,
        audit_sink=audit_sink or _FailClosedAuditSink(),
        clock=lambda: datetime.now(UTC),
    )


__all__ = (
    "OpaqueSessionManager",
    "SqlAlchemyIdentityTransactionFactory",
    "build_identity_service",
)
