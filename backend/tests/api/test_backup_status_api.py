from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fastapi.testclient import TestClient

from app.identity.application.service import AuthenticatedPrincipal
from app.main import create_app
from app.recovery.application.status import BackupStatusQuery


@dataclass(frozen=True)
class Snapshot:
    last_valid_date: date | None
    last_failure_date: date | None
    verification_status: str
    failure_detail: str | None = None


class Reader:
    def __init__(self, snapshot: Snapshot | None = None) -> None:
        self._snapshot = snapshot or Snapshot(date(2026, 7, 22), None, "verified")

    def read(self) -> Snapshot:
        return self._snapshot


class Session:
    def authenticate(
        self, session_token: str, *, at: object = None
    ) -> AuthenticatedPrincipal | None:
        del at
        if session_token == "session":
            return AuthenticatedPrincipal("user", "space", "owner")
        return None

    def validate_csrf(self, session_token: str, csrf_token: str) -> bool:
        del session_token, csrf_token
        return False


def test_backup_status_requires_authentication() -> None:
    response = TestClient(create_app(readiness_probe=lambda: True)).get(
        "/api/v1/recovery/backup-status"
    )

    assert response.status_code == 401


def test_backup_surface_is_read_only_and_has_no_restore_contract() -> None:
    schema = create_app(readiness_probe=lambda: True).openapi()
    path = schema["paths"]["/api/v1/recovery/backup-status"]

    assert set(path) == {"get"}
    serialized = str(schema).lower()
    assert "restore" not in serialized
    assert "file_path" not in serialized
    assert "upload" not in serialized


def test_backup_status_projects_only_allowlisted_metadata() -> None:
    domestic_dates = iter((date(2026, 7, 23), date(2026, 7, 24)))
    app = create_app(
        readiness_probe=lambda: True,
        session_manager=Session(),
        allowed_origin="https://finance.test",
        backup_status_query=BackupStatusQuery(
            Reader(),
            today=lambda: next(domestic_dates),
            retention_count=7,
        ),
    )
    client = TestClient(app, base_url="https://finance.test")
    client.cookies.set("__Host-pf_session", "session")

    first = client.get("/api/v1/recovery/backup-status")
    second = client.get("/api/v1/recovery/backup-status")

    assert first.status_code == 200
    assert first.json() == {
        "state": "VERIFIED",
        "last_valid_backup_date": "2026-07-22",
        "last_verification_failure_date": None,
        "verification_result": "PASSED",
        "failure_detail": None,
        "next_expected_execution_date": "2026-07-24",
        "retention_count": 7,
    }
    assert second.json()["next_expected_execution_date"] == "2026-07-25"


def test_failed_backup_status_exposes_only_closed_failure_detail() -> None:
    app = create_app(
        readiness_probe=lambda: True,
        session_manager=Session(),
        allowed_origin="https://finance.test",
        backup_status_query=BackupStatusQuery(
            Reader(
                Snapshot(
                    date(2026, 7, 20),
                    date(2026, 7, 22),
                    "failed",
                    "BACKUP_ATTEMPT_FAILED",
                )
            ),
            today=lambda: date(2026, 7, 23),
            retention_count=7,
        ),
    )
    client = TestClient(app, base_url="https://finance.test")
    client.cookies.set("__Host-pf_session", "session")

    response = client.get("/api/v1/recovery/backup-status")

    assert response.status_code == 200
    assert response.json()["failure_detail"] == "BACKUP_ATTEMPT_FAILED"
    assert "path" not in str(response.json()).lower()
