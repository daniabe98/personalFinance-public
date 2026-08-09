from __future__ import annotations

from app.identity.application.service import IdentityService
from app.main import create_app


def test_openapi_exposes_only_versioned_closed_finance_routes() -> None:
    schema = create_app(readiness_probe=lambda: True).openapi()
    paths = schema["paths"]

    expected = {
        "/api/v1/accounts",
        "/api/v1/categories",
        "/api/v1/transactions",
        "/api/v1/transactions/opening",
        "/api/v1/transactions/income",
        "/api/v1/transactions/expense",
        "/api/v1/transactions/transfer",
        "/api/v1/reconciliations/candidates",
        "/api/v1/reconciliations/preview",
        "/api/v1/reports/economic",
        "/api/v1/reports/cash-flow",
        "/api/v1/reports/net-worth",
        "/api/v1/audit/events",
    }
    assert expected <= set(paths)
    assert all(path.startswith(("/api/v1/", "/health/")) for path in paths)
    serialized = str(schema).lower()
    assert "debit" not in serialized
    assert "credit" not in serialized
    assert "restore" not in serialized
    assert "bearer" not in serialized


def test_openapi_money_fields_are_integers_and_commands_have_idempotency_header() -> None:
    schema = create_app(readiness_probe=lambda: True).openapi()
    components = schema["components"]["schemas"]
    money_fields = [
        field
        for model in components.values()
        for name, field in model.get("properties", {}).items()
        if name.endswith("_cents")
    ]
    assert money_fields
    assert all(
        field.get("type") == "integer" or {"type": "integer"} in field.get("anyOf", [])
        for field in money_fields
    )
    operation = schema["paths"]["/api/v1/transactions/opening"]["post"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in operation["parameters"])
    assert any(
        parameter["name"] == "X-CSRF-Token" and parameter["required"]
        for parameter in operation["parameters"]
    )
    security_schemes = schema["components"]["securitySchemes"]
    assert security_schemes["APIKeyCookie"]["in"] == "cookie"
    assert security_schemes["APIKeyCookie"]["name"] == "__Host-pf_session"


def test_session_contract_describes_the_csrf_token_returned_to_memory() -> None:
    schema = create_app(
        readiness_probe=lambda: True,
        identity_service=object.__new__(IdentityService),
        session_manager=object(),
        allowed_origin="https://finance.test",
    ).openapi()

    operation = schema["paths"]["/api/v1/auth/session"]["get"]
    assert operation["description"] == "Return the principal and its stable CSRF token."


def test_transaction_response_exposes_safe_read_details_without_entries() -> None:
    schema = create_app(readiness_probe=lambda: True).openapi()
    transaction = schema["components"]["schemas"]["TransactionResponse"]
    properties = transaction["properties"]

    assert {
        "amount_cents",
        "account_id",
        "category_id",
        "destination_account_id",
        "corrected_original_transaction_id",
    } <= set(properties)
    assert {"type": "integer"} in properties["amount_cents"]["anyOf"]
    for identifier in ("account_id", "category_id", "destination_account_id"):
        assert {"type": "string"} in properties[identifier]["anyOf"]
    assert "entries" not in properties
