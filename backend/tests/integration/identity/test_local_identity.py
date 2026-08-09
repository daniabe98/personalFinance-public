from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Self

import pytest

from app.identity.application.service import (
    AuthenticationFailedError,
    BootstrapAlreadyCompletedError,
    IdentityService,
    SessionGrant,
)
from app.identity.domain.user import PersonalSpace, User

NOW = datetime(2026, 7, 23, 18, 0, tzinfo=UTC)
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a different correct horse battery staple"


@dataclass
class IdentityState:
    users: dict[str, User] = field(default_factory=dict)
    spaces: dict[str, PersonalSpace] = field(default_factory=dict)
    revoked_user_ids: list[str] = field(default_factory=list)


class FakeIdentityRepository:
    def __init__(self, state: IdentityState) -> None:
        self.state = state

    def has_any_user(self) -> bool:
        return bool(self.state.users)

    def add_user(self, user: User) -> None:
        self.state.users[user.id] = user

    def add_space(self, space: PersonalSpace) -> None:
        self.state.spaces[space.id] = space

    def user_by_username(self, username: str) -> User | None:
        return next(
            (user for user in self.state.users.values() if user.username == username),
            None,
        )

    def only_user(self) -> User | None:
        return next(iter(self.state.users.values()), None)

    def space_for_user(self, user_id: str) -> PersonalSpace | None:
        return next(
            (space for space in self.state.spaces.values() if space.owner_user_id == user_id),
            None,
        )

    def update_user(self, user: User) -> None:
        self.state.users[user.id] = user

    def revoke_sessions(self, user_id: str, revoked_at: datetime) -> None:
        assert revoked_at.tzinfo is UTC
        self.state.revoked_user_ids.append(user_id)


class FakeTransaction:
    def __init__(self, committed: IdentityState) -> None:
        self._committed = committed
        self._working = deepcopy(committed)
        self.identity = FakeIdentityRepository(self._working)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> bool:
        del exception_type, exception, traceback
        return False

    def commit(self) -> None:
        self._committed.users = self._working.users
        self._committed.spaces = self._working.spaces
        self._committed.revoked_user_ids = self._working.revoked_user_ids


class FakeSessionGateway:
    def __init__(self) -> None:
        self.created: list[tuple[str, str, datetime]] = []
        self.revoked_tokens: list[str] = []

    def create(
        self,
        *,
        user_id: str,
        space_id: str,
        now: datetime,
    ) -> SessionGrant:
        self.created.append((user_id, space_id, now))
        return SessionGrant(
            session_token=f"session-{len(self.created)}",
            csrf_token=f"csrf-{len(self.created)}",
            expires_at=now + timedelta(hours=12),
            principal_user_id=user_id,
            principal_space_id=space_id,
        )

    def revoke(self, session_token: str, revoked_at: datetime) -> bool:
        assert revoked_at.tzinfo is UTC
        self.revoked_tokens.append(session_token)
        return True


class RecordingAuditSink:
    def __init__(self) -> None:
        self.events: list[dict[str, str | None]] = []

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


@pytest.fixture
def identity_components() -> tuple[
    IdentityService,
    IdentityState,
    FakeSessionGateway,
    RecordingAuditSink,
]:
    from app.identity.adapters.passwords import Argon2PasswordHasher

    state = IdentityState()
    sessions = FakeSessionGateway()
    audit = RecordingAuditSink()
    service = IdentityService(
        transaction_factory=lambda: FakeTransaction(state),
        password_hasher=Argon2PasswordHasher(),
        sessions=sessions,
        audit_sink=audit,
        clock=lambda: NOW,
    )
    return service, state, sessions, audit


def test_bootstrap_creates_exactly_one_user_and_personal_space_atomically(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    service, state, _, _ = identity_components

    principal = service.bootstrap(
        username="owner",
        password=PASSWORD,
        space_name="Personal",
    )

    assert len(state.users) == 1
    assert len(state.spaces) == 1
    assert principal.user_id in state.users
    assert principal.space_id in state.spaces
    assert state.spaces[principal.space_id].owner_user_id == principal.user_id


def test_bootstrap_rejects_a_second_local_account(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    service, state, _, _ = identity_components
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")

    with pytest.raises(BootstrapAlreadyCompletedError):
        service.bootstrap(username="other", password=PASSWORD, space_name="Other")

    assert len(state.users) == 1
    assert len(state.spaces) == 1


def test_password_is_stored_as_argon2id_and_can_be_verified(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    from app.identity.adapters.passwords import Argon2PasswordHasher

    service, state, _, _ = identity_components
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    stored_hash = next(iter(state.users.values())).password_hash

    assert stored_hash.startswith("$argon2id$")
    assert PASSWORD not in stored_hash
    assert Argon2PasswordHasher().verify(PASSWORD, stored_hash)


@pytest.mark.parametrize(
    ("username", "password"),
    [("missing", PASSWORD), ("owner", "wrong password")],
)
def test_login_uses_one_generic_invalid_credential_error(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
    username: str,
    password: str,
) -> None:
    service, _, _, audit = identity_components
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    correlation_id = "attempt-1"

    with pytest.raises(AuthenticationFailedError) as caught:
        service.login(username=username, password=password, correlation_id=correlation_id)

    assert str(caught.value) == "invalid credentials"
    assert audit.events[-1] == {
        "action": "LOGIN",
        "result": "FAILURE",
        "actor_id": None,
        "space_id": None,
        "correlation_id": correlation_id,
    }


def test_login_returns_utc_expiring_session_without_password_material(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    service, _, _, audit = identity_components
    principal = service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")

    grant = service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="attempt-2",
    )

    assert grant.expires_at.tzinfo is UTC
    assert grant.principal_user_id == principal.user_id
    assert grant.principal_space_id == principal.space_id
    assert PASSWORD not in repr(grant)
    assert audit.events[-1]["result"] == "SUCCESS"


def test_logout_revokes_the_presented_session(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    service, _, sessions, audit = identity_components
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    grant = service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="attempt-3",
    )

    service.logout(
        session_token=grant.session_token,
        principal_user_id=grant.principal_user_id,
        principal_space_id=grant.principal_space_id,
        correlation_id="logout-1",
    )

    assert sessions.revoked_tokens == [grant.session_token]
    assert audit.events[-1]["action"] == "LOGOUT"


def test_reset_rehashes_password_and_revokes_every_existing_session(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
) -> None:
    service, state, _, audit = identity_components
    principal = service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    previous_hash = state.users[principal.user_id].password_hash
    correlation_id = "reset-1"

    service.reset_credentials(new_password=NEW_PASSWORD, correlation_id=correlation_id)

    user = state.users[principal.user_id]
    assert user.password_hash != previous_hash
    assert user.credential_version == 2
    assert state.revoked_user_ids == [principal.user_id]
    assert audit.events[-1] == {
        "action": "CREDENTIAL_RESET",
        "result": "SUCCESS",
        "actor_id": principal.user_id,
        "space_id": principal.space_id,
        "correlation_id": correlation_id,
    }


def test_session_adapter_enforces_expiry_and_bulk_revocation() -> None:
    from app.identity.adapters.sessions import OpaqueSessionManager

    assert OpaqueSessionManager


def test_cli_commands_use_hidden_prompt(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.cli import app

    service, state, _, _ = identity_components
    prompted: list[str] = []
    secrets = iter((PASSWORD, PASSWORD, NEW_PASSWORD, NEW_PASSWORD))

    def hidden_prompt(prompt: str) -> str:
        prompted.append(prompt)
        return next(secrets)

    assert (
        app(
            ["bootstrap", "--username", "owner", "--space-name", "Personal"],
            service=service,
            password_prompt=hidden_prompt,
        )
        == 0
    )
    assert app(["reset-credentials"], service=service, password_prompt=hidden_prompt) == 0
    output = capsys.readouterr()

    assert len(prompted) == 4
    assert all("password" in prompt.lower() for prompt in prompted)
    assert PASSWORD not in output.out + output.err
    assert NEW_PASSWORD not in output.out + output.err
    assert not any(user.password_hash in output.out + output.err for user in state.users.values())


def test_cli_second_bootstrap_fails_closed_with_distinct_exit_code(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.cli import app

    service, _, _, _ = identity_components

    def prompt(_label: str) -> str:
        return PASSWORD

    command = ["bootstrap", "--username", "owner", "--space-name", "Personal"]
    assert app(command, service=service, password_prompt=prompt) == 0

    assert app(command, service=service, password_prompt=prompt) == 2
    output = capsys.readouterr()

    assert "already configured" in output.err
    assert PASSWORD not in output.out + output.err


def test_cli_reset_revokes_sessions_and_never_outputs_bearer_material(
    identity_components: tuple[
        IdentityService,
        IdentityState,
        FakeSessionGateway,
        RecordingAuditSink,
    ],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.cli import app

    service, state, _, _ = identity_components
    service.bootstrap(username="owner", password=PASSWORD, space_name="Personal")
    grant = service.login(
        username="owner",
        password=PASSWORD,
        correlation_id="pre-reset",
    )
    prompts = iter((NEW_PASSWORD, NEW_PASSWORD))

    assert (
        app(
            ["reset-credentials"],
            service=service,
            password_prompt=lambda _label: next(prompts),
        )
        == 0
    )
    output = capsys.readouterr()

    assert state.revoked_user_ids
    assert grant.session_token not in output.out + output.err
    assert grant.csrf_token not in output.out + output.err
