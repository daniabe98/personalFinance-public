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


class Reader:
    def read(self) -> Snapshot:
        return Snapshot(date(2026, 7, 22), None, "verified")


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
    app = create_app(
        readiness_probe=lambda: True,
        session_manager=Session(),
        allowed_origin="https://finance.test",
        backup_status_query=BackupStatusQuery(
            Reader(),
            domestic_date=date(2026, 7, 23),
            retention_count=7,
        ),
    )
    client = TestClient(app, base_url="https://finance.test")
    client.cookies.set("__Host-pf_session", "session")

    response = client.get("/api/v1/recovery/backup-status")

    assert response.status_code == 200
    assert response.json() == {
        "state": "VERIFIED",
        "last_valid_backup_date": "2026-07-22",
        "last_verification_failure_date": None,
        "verification_result": "PASSED",
        "domestic_date": "2026-07-23",
        "retention_count": 7,
    }
