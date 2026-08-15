from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit.application.service import AuditQueryService
from app.identity.application.service import AuthenticatedPrincipal
from app.main import create_app
from app.reconciliation.application.service import ReconciliationService
from app.reporting.application.queries import ReportQueryService
from app.shared.config import Settings
from app.shared.database import Base

ORIGIN = "https://finance.test"
COOKIE = "__Host-pf_session"


@pytest.fixture
def composed_finance_app(tmp_path: Path) -> Iterator[tuple[FastAPI, TestClient]]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'finance-api.db'}",
        secret_key="x" * 32,
    )
    application = create_app(
        settings=settings,
        readiness_probe=lambda: True,
        allowed_origin=ORIGIN,
    )
    Base.metadata.create_all(application.state.database_engine)
    application.state.identity_service.bootstrap(
        username="owner",
        password="correct horse battery staple",
        space_name="Personal",
    )
    with TestClient(application, base_url=ORIGIN) as client:
        yield application, client


@dataclass
class SessionStub:
    csrf: str = "csrf-token"

    def authenticate(
        self, session_token: str, *, at: object = None
    ) -> AuthenticatedPrincipal | None:
        del at
        if session_token != "session-token":
            return None
        return AuthenticatedPrincipal("user-1", "space-1", "owner")

    def validate_csrf(self, session_token: str, csrf_token: str) -> bool:
        return session_token == "session-token" and csrf_token == self.csrf


def test_finance_surface_requires_authentication() -> None:
    client = TestClient(
        create_app(
            readiness_probe=lambda: True,
            session_manager=SessionStub(),
            allowed_origin=ORIGIN,
        )
    )

    response = client.get("/api/v1/accounts")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "authentication_required"


def test_unsafe_finance_surface_requires_exact_origin_and_csrf() -> None:
    client = TestClient(
        create_app(
            readiness_probe=lambda: True,
            session_manager=SessionStub(),
            allowed_origin=ORIGIN,
        )
    )
    client.cookies.set(COOKIE, "session-token")
    payload = {
        "name": "Bank",
        "kind": "ASSET",
        "is_reconcilable": True,
    }

    missing_origin = client.post("/api/v1/accounts", json=payload)
    missing_csrf = client.post(
        "/api/v1/accounts",
        json=payload,
        headers={"Origin": ORIGIN},
    )

    assert missing_origin.status_code == 403
    assert missing_csrf.status_code == 403


def test_money_rejects_non_integer_cents() -> None:
    client = TestClient(
        create_app(
            readiness_probe=lambda: True,
            session_manager=SessionStub(),
            allowed_origin=ORIGIN,
        )
    )
    client.cookies.set(COOKIE, "session-token")
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": "csrf-token",
        "Idempotency-Key": "opening-1",
    }

    response = client.post(
        "/api/v1/transactions/opening",
        json={
            "account_id": "account-1",
            "amount_cents": True,
            "economic_date": "2026-07-23",
            "description": "Opening balance",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


@pytest.mark.parametrize(
    "description_payload",
    [
        {},
        {"description": None},
        {"description": ""},
        {"description": "   "},
        {"description": "x" * 501},
    ],
)
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/transactions/opening",
            {
                "account_id": "account-1",
                "amount_cents": 100,
                "economic_date": "2026-07-23",
            },
        ),
        (
            "/api/v1/transactions/income",
            {
                "account_id": "account-1",
                "category_id": "category-1",
                "amount_cents": 100,
                "economic_date": "2026-07-23",
            },
        ),
        (
            "/api/v1/transactions/expense",
            {
                "account_id": "account-1",
                "category_id": "category-1",
                "amount_cents": 100,
                "economic_date": "2026-07-23",
            },
        ),
        (
            "/api/v1/transactions/transfer",
            {
                "source_account_id": "account-1",
                "destination_account_id": "account-2",
                "amount_cents": 100,
                "economic_date": "2026-07-23",
            },
        ),
        (
            "/api/v1/transactions/drafts",
            {
                "kind": "INCOME",
                "account_id": "account-1",
                "category_id": "category-1",
                "amount_cents": 100,
                "economic_date": "2026-07-23",
            },
        ),
    ],
)
def test_transaction_writes_reject_invalid_description(
    path: str,
    payload: dict[str, object],
    description_payload: dict[str, object],
) -> None:
    client = TestClient(
        create_app(
            readiness_probe=lambda: True,
            session_manager=SessionStub(),
            allowed_origin=ORIGIN,
        )
    )
    client.cookies.set(COOKIE, "session-token")
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": "csrf-token",
        "Idempotency-Key": "invalid-description",
    }

    response = client.post(path, json={**payload, **description_payload}, headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_composition_uses_real_services_and_durable_audit(
    composed_finance_app: tuple[FastAPI, TestClient],
) -> None:
    app, client = composed_finance_app
    assert isinstance(app.state.reconciliation_service, ReconciliationService)
    assert isinstance(app.state.report_query_service, ReportQueryService)
    assert isinstance(app.state.audit_query_service, AuditQueryService)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "owner",
            "password": "correct horse battery staple",
        },
        headers={"Origin": ORIGIN},
    )
    csrf = login.json()["csrf_token"]
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}

    account = client.post(
        "/api/v1/accounts",
        json={"name": "Bank", "kind": "ASSET", "is_reconcilable": True},
        headers=headers,
    )
    opening = client.post(
        "/api/v1/transactions/opening",
        json={
            "account_id": account.json()["id"],
            "amount_cents": 100_00,
            "economic_date": "2026-07-23",
            "description": "  Initial balance  ",
        },
        headers={**headers, "Idempotency-Key": "opening-real-1"},
    )
    second_account = client.post(
        "/api/v1/accounts",
        json={"name": "Savings", "kind": "ASSET", "is_reconcilable": True},
        headers=headers,
    )
    category = client.post(
        "/api/v1/categories",
        json={"name": "Salary", "kind": "INCOME"},
        headers=headers,
    )
    income = client.post(
        "/api/v1/transactions/income",
        json={
            "account_id": account.json()["id"],
            "category_id": category.json()["id"],
            "amount_cents": 250_00,
            "economic_date": "2026-07-23",
            "description": "  Salary  ",
        },
        headers={**headers, "Idempotency-Key": "income-real-1"},
    )
    transfer = client.post(
        "/api/v1/transactions/transfer",
        json={
            "source_account_id": account.json()["id"],
            "destination_account_id": second_account.json()["id"],
            "amount_cents": 50_00,
            "economic_date": "2026-07-23",
            "description": "  Move to savings  ",
        },
        headers={**headers, "Idempotency-Key": "transfer-real-1"},
    )
    draft = client.post(
        "/api/v1/transactions/drafts",
        json={
            "kind": "INCOME",
            "account_id": account.json()["id"],
            "category_id": category.json()["id"],
            "amount_cents": 75_25,
            "economic_date": "2026-07-24",
            "cash_date": "2026-07-25",
            "description": "Next salary",
        },
        headers=headers,
    )
    history = client.get("/api/v1/transactions")
    opening_detail = client.get(f"/api/v1/transactions/{opening.json()['transaction_id']}")
    audit = client.get("/api/v1/audit/events")

    assert login.status_code == 200
    assert account.status_code == 201
    assert opening.status_code == 200
    assert income.status_code == 200
    assert transfer.status_code == 200
    assert draft.status_code == 201
    assert opening.json()["status"] == "POSTED"
    assert history.status_code == 200
    by_kind = {transaction["kind"]: transaction for transaction in history.json()}
    assert by_kind["OPENING"] == {
        **by_kind["OPENING"],
        "description": "Initial balance",
        "amount_cents": 100_00,
        "account_id": account.json()["id"],
        "category_id": None,
        "destination_account_id": None,
    }
    assert by_kind["INCOME"] == {
        **by_kind["INCOME"],
        "description": "Salary",
        "amount_cents": 250_00,
        "account_id": account.json()["id"],
        "category_id": category.json()["id"],
        "destination_account_id": None,
    }
    assert by_kind["TRANSFER"] == {
        **by_kind["TRANSFER"],
        "description": "Move to savings",
        "amount_cents": 50_00,
        "account_id": account.json()["id"],
        "category_id": None,
        "destination_account_id": second_account.json()["id"],
    }
    draft_view = next(
        transaction for transaction in history.json() if transaction["id"] == draft.json()["id"]
    )
    assert draft_view == {
        **draft_view,
        "status": "DRAFT",
        "amount_cents": 75_25,
        "account_id": account.json()["id"],
        "category_id": category.json()["id"],
        "destination_account_id": None,
        "cash_date": "2026-07-25",
    }
    assert "entries" not in str(history.json()).lower()
    assert opening_detail.json()["amount_cents"] == 100_00
    assert opening_detail.json()["account_id"] == account.json()["id"]
    assert any(event["action"] == "POSTING" for event in audit.json()["events"])
