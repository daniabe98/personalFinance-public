from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_audit_events_require_authentication() -> None:
    response = TestClient(create_app(readiness_probe=lambda: True)).get("/api/v1/audit/events")

    assert response.status_code == 401


def test_audit_openapi_has_no_free_form_payload_or_secrets() -> None:
    schema = create_app(readiness_probe=lambda: True).openapi()
    operation = schema["paths"]["/api/v1/audit/events"]["get"]
    serialized = str(operation).lower()

    assert "payload" not in serialized
    assert "password" not in serialized
    assert "token" not in serialized
