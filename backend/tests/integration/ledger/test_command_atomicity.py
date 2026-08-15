from __future__ import annotations

from datetime import date

import pytest

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import CreateAccount, CreateCategory, IncomeCommand
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.ports.audit import NullFinancialAuditSink
from app.shared.idempotency import IdempotencyConflictError
from tests.support.ledger import SPACE_ID


class FailSuccessAudit:
    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        transaction_id: str | None,
        correlation_id: str,
    ) -> None:
        del session, action, space_id, transaction_id, correlation_id
        if outcome == "SUCCESS":
            raise RuntimeError("injected audit failure")


def test_failure_rolls_back_transaction_entries_and_idempotency(ledger_uow_factory) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    command = IncomeCommand(
        SPACE_ID,
        account.id,
        category.id,
        500,
        date(2026, 7, 1),
        None,
        "Salary",
        "same-key",
    )

    failing = FinancialCommandService(uow_factory, SqlAlchemyLedgerRepository, FailSuccessAudit())
    with pytest.raises(RuntimeError, match="injected audit failure"):
        failing.create_income(command)
    assert failing.list_transactions(SPACE_ID) == ()

    healthy = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    result = healthy.create_income(command)
    replay = healthy.create_income(command)
    assert replay.transaction_id == result.transaction_id
    assert replay.replayed is True

    changed = IncomeCommand(
        SPACE_ID,
        account.id,
        category.id,
        501,
        date(2026, 7, 1),
        None,
        "Salary",
        "same-key",
    )
    with pytest.raises(IdempotencyConflictError):
        healthy.create_income(changed)
