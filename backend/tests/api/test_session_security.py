from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.identity.adapters.sessions import OpaqueSessionManager
from app.identity.application.service import IdentityService
from app.shared.config import Settings
from app.shared.database import (
    Base,
    SessionFactory,
    create_engine,
    create_session_factory,
    register_orm_models,
)
from app.shared.models_identity import SessionRecord

NOW = datetime(2026, 7, 23, 19, 0, tzinfo=UTC)
PASSWORD = "correct horse battery staple"
ORIGIN = "https://finance.test"
COOKIE_NAME = "__Host-pf_session"
HTTP_ORIGIN = "http://192.168.1.50:8080"
HTTP_COOKIE_NAME = "pf_session"


@dataclass
class RecordingAuditSink:
    events: list[dict[str, str | None]] = field(default_factory=list)

    def record_authentication(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None:
        self.events.append(
            {
                "action": action,
                "result": result,
                "actor_id": actor_id,
                "space_id": space_id,
                "correlation_id": correlation_id,
            }
        )


@dataclass(frozen=True)
class SessionHarness:
    service: IdentityService
    sessions: OpaqueSessionManager
    session_factory: SessionFactory
    audit: RecordingAuditSink


@pytest.fixture
def session_harness(tmp_path: Path) -> Iterator[SessionHarness]:
    from app.identity.adapters.passwords import Argon2PasswordHasher
    from app.identity.adapters.sessions import (
        OpaqueSessionManager,
        SqlAlchemyIdentityTransactionFactory,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    register_orm_models()

    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    sessions = OpaqueSessionManager(
        session_factory,
        lifetime=timedelta(hours=12),
        clock=lambda: NOW,
    )
    audit = RecordingAuditSink()
    service = IdentityService(
        transaction_factory=SqlAlchemyIdentityTransactionFactory(session_factory),
        password_hasher=Argon2PasswordHasher(),
        sessions=sessions,
        audit_sink=audit,
        clock=lambda: NOW,
    )
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    yield SessionHarness(service, sessions, session_factory, audit)
    engine.dispose()


@dataclass(frozen=True)
class SecurityHarness(SessionHarness):
    client: TestClient


@pytest.fixture
def security_harness(
    tmp_path: Path,
    session_harness: SessionHarness,
) -> Iterator[SecurityHarness]:
    from app.main import create_app

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'identity.db'}",
        secret_key="s" * 32,
    )
    application = create_app(
        settings=settings,
        readiness_probe=lambda: True,
        identity_service=session_harness.service,
        session_manager=session_harness.sessions,
        allowed_origin=ORIGIN,
    )
    with TestClient(application, base_url=ORIGIN) as client:
        yield SecurityHarness(
            session_harness.service,
            session_harness.sessions,
            session_harness.session_factory,
            session_harness.audit,
            client,
        )


def _login(harness: SecurityHarness) -> tuple[str, str]:
    response = harness.client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    return response.cookies[COOKIE_NAME], response.json()["csrf_token"]


def test_login_sets_exact_strict_host_cookie_and_returns_no_bearer_secret(
    security_harness: SecurityHarness,
) -> None:
    response = security_harness.client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    assert "session_token" not in response.text
    assert PASSWORD not in response.text


def test_explicit_http_lan_mode_uses_non_secure_strict_cookie(
    tmp_path: Path,
    session_harness: SessionHarness,
) -> None:
    from app.main import create_app

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'identity.db'}",
        secret_key="s" * 32,
        transport_mode="http_lan",
    )
    application = create_app(
        settings=settings,
        readiness_probe=lambda: True,
        identity_service=session_harness.service,
        session_manager=session_harness.sessions,
        allowed_origin=HTTP_ORIGIN,
    )

    with TestClient(application, base_url=HTTP_ORIGIN) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": PASSWORD},
            headers={"Origin": HTTP_ORIGIN},
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{HTTP_COOKIE_NAME}=")
        assert "Secure" not in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie
        assert response.cookies[HTTP_COOKIE_NAME]
        assert client.get("/api/v1/auth/session").status_code == 200

        csrf_token = response.json()["csrf_token"]
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": HTTP_ORIGIN, "X-CSRF-Token": csrf_token},
        )
        assert logout.status_code == 204
        expired_cookie = logout.headers["set-cookie"]
        assert expired_cookie.startswith(f'{HTTP_COOKIE_NAME}=""')
        assert "Secure" not in expired_cookie


def test_https_mode_rejects_non_loopback_http_origin(
    tmp_path: Path,
    session_harness: SessionHarness,
) -> None:
    from app.main import create_app

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'identity.db'}",
        secret_key="s" * 32,
    )
    application = create_app(
        settings=settings,
        readiness_probe=lambda: True,
        identity_service=session_harness.service,
        session_manager=session_harness.sessions,
        allowed_origin=HTTP_ORIGIN,
    )

    with TestClient(application, base_url=HTTP_ORIGIN) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": PASSWORD},
            headers={"Origin": HTTP_ORIGIN},
        )

    assert response.status_code == 403


@pytest.mark.parametrize("host", ["169.254.1.10", "192.0.2.10", "8.8.8.8"])
def test_http_lan_mode_rejects_addresses_outside_rfc1918(
    host: str,
    tmp_path: Path,
    session_harness: SessionHarness,
) -> None:
    from app.main import create_app

    origin = f"http://{host}:8080"
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'identity.db'}",
        secret_key="s" * 32,
        transport_mode="http_lan",
    )
    application = create_app(
        settings=settings,
        readiness_probe=lambda: True,
        identity_service=session_harness.service,
        session_manager=session_harness.sessions,
        allowed_origin=origin,
    )

    with TestClient(application, base_url=origin) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": PASSWORD},
            headers={"Origin": origin},
        )

    assert response.status_code == 403


def test_only_fixed_length_one_way_token_and_csrf_digests_are_stored(
    session_harness: SessionHarness,
) -> None:
    grant = session_harness.service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="digest-test",
    )

    with session_harness.session_factory() as database:
        record = database.scalar(select(SessionRecord))

    assert record is not None
    assert len(record.token_hash) == 64
    assert len(record.csrf_token_hash) == 64
    assert grant.session_token not in (record.token_hash, record.csrf_token_hash)
    assert grant.csrf_token not in (record.token_hash, record.csrf_token_hash)


def test_csrf_is_bound_to_the_active_session(
    session_harness: SessionHarness,
) -> None:
    first = session_harness.service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="csrf-1",
    )
    second = session_harness.service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="csrf-2",
    )
    sessions = session_harness.sessions

    assert sessions.validate_csrf(first.session_token, first.csrf_token)
    assert sessions.validate_csrf(second.session_token, second.csrf_token)
    assert not sessions.validate_csrf(first.session_token, second.csrf_token)
    assert not sessions.validate_csrf(second.session_token, first.csrf_token)


@pytest.mark.parametrize("origin", [None, "https://evil.test", "null", "not-an-origin"])
def test_logout_rejects_missing_malformed_or_cross_origin(
    security_harness: SecurityHarness,
    origin: str | None,
) -> None:
    _, csrf = _login(security_harness)
    headers = {"X-CSRF-Token": csrf}
    if origin is not None:
        headers["Origin"] = origin

    response = security_harness.client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 403


def test_unsafe_request_rejects_missing_or_mismatched_protection(
    security_harness: SecurityHarness,
) -> None:
    _, csrf = _login(security_harness)

    missing = security_harness.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN},
    )
    mismatched = security_harness.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": f"{csrf}-wrong"},
    )

    assert missing.status_code == 403
    assert mismatched.status_code == 403


def test_unauthorized_session_query_is_rejected(
    security_harness: SecurityHarness,
) -> None:
    security_harness.client.cookies.clear()

    response = security_harness.client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}


def test_current_session_keeps_csrf_valid_across_reload_and_tabs(
    security_harness: SecurityHarness,
) -> None:
    session_token, login_csrf = _login(security_harness)

    first_tab = security_harness.client.get("/api/v1/auth/session")
    second_tab = security_harness.client.get("/api/v1/auth/session")

    assert first_tab.status_code == second_tab.status_code == 200
    assert set(first_tab.json()) == {"user_id", "space_id", "username", "csrf_token"}
    assert first_tab.json()["csrf_token"] == second_tab.json()["csrf_token"] == login_csrf
    assert security_harness.sessions.validate_csrf(session_token, first_tab.json()["csrf_token"])
    logout = security_harness.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": login_csrf},
    )
    assert logout.status_code == 204


def test_expiry_and_revocation_make_tokens_unusable(
    session_harness: SessionHarness,
) -> None:
    grant = session_harness.service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="expiry-test",
    )
    sessions = session_harness.sessions

    assert sessions.authenticate(grant.session_token, at=NOW) is not None
    assert sessions.authenticate(grant.session_token, at=NOW + timedelta(hours=12)) is None
    assert sessions.revoke(grant.session_token, NOW)
    assert sessions.authenticate(grant.session_token, at=NOW) is None


def test_credential_reset_revokes_every_persisted_session(
    session_harness: SessionHarness,
) -> None:
    grant = session_harness.service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="before-reset",
    )

    session_harness.service.reset_credentials(
        new_password="another secure local password",
        correlation_id="reset-all",
    )

    assert session_harness.sessions.authenticate(grant.session_token, at=NOW) is None


def test_logout_clears_cookie_and_revokes_session(
    security_harness: SecurityHarness,
) -> None:
    token, csrf = _login(security_harness)

    response = security_harness.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
    )

    assert response.status_code == 204
    assert f"{COOKIE_NAME}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert security_harness.sessions.authenticate(token, at=NOW) is None


def test_login_failure_is_generic_and_audit_contains_no_secret(
    security_harness: SecurityHarness,
) -> None:
    missing = security_harness.client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": "wrong"},
        headers={"Origin": ORIGIN},
    )
    wrong = security_harness.client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "wrong"},
        headers={"Origin": ORIGIN},
    )

    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json() == {"detail": "invalid credentials"}
    serialized_events = repr(security_harness.audit.events)
    assert "wrong" not in serialized_events
    assert PASSWORD not in serialized_events
    allowed_keys = {"action", "result", "actor_id", "space_id", "correlation_id"}
    assert all(set(event) == allowed_keys for event in security_harness.audit.events)


def test_bootstrap_and_reset_have_no_http_route(
    security_harness: SecurityHarness,
) -> None:
    assert security_harness.client.post("/api/v1/auth/bootstrap").status_code == 404
    assert security_harness.client.post("/api/v1/auth/reset-credentials").status_code == 404
