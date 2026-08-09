from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.shared.config import Settings


def _settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        secret_key="test-secret-value-with-at-least-32-characters",
    )


def test_liveness_reports_process_health_without_touching_database() -> None:
    def unexpected_probe() -> bool:
        raise AssertionError("liveness must not probe dependencies")

    client = TestClient(create_app(settings=_settings(), readiness_probe=unexpected_probe))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_available_database() -> None:
    client = TestClient(create_app(settings=_settings(), readiness_probe=lambda: True))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_degrades_without_claiming_success() -> None:
    client = TestClient(create_app(settings=_settings(), readiness_probe=lambda: False))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_readiness_degrades_when_probe_raises() -> None:
    def failed_probe() -> bool:
        raise RuntimeError("database location is intentionally omitted")

    client = TestClient(create_app(settings=_settings(), readiness_probe=failed_probe))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
