from __future__ import annotations

from datetime import date

import pytest

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    DraftCommand,
    IncomeCommand,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.application.queries import LedgerQueryService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.errors import EntityNotFoundError
from app.ledger.domain.transaction import TransactionKind
from app.ledger.ports.audit import NullFinancialAuditSink
from tests.support.ledger import OTHER_SPACE_ID, SPACE_ID


def test_queries_are_same_space_immutable_deterministic_and_ledger_derived(
    ledger_uow_factory,
) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    commands = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    queries = LedgerQueryService(uow_factory, SqlAlchemyLedgerRepository)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    result = commands.create_income(
        IncomeCommand(
            SPACE_ID,
            account.id,
            category.id,
            750,
            date(2026, 7, 1),
            date(2026, 7, 2),
            "Salary",
            "query-income",
        )
    )
    catalog.set_account_archived(SPACE_ID, account.id, True)

    assert queries.list_accounts(SPACE_ID, include_archived=False) == ()
    account_view = queries.list_accounts(SPACE_ID, include_archived=True)[0]
    transaction = queries.get_transaction(SPACE_ID, result.transaction_id)
    history = queries.list_transactions(SPACE_ID, limit=10, offset=0)

    assert account_view.balance_cents == 750
    assert account_view.is_archived is True
    assert transaction.status_label == "Contabilizado"
    assert len(transaction.entries) == 2
    assert history == (transaction,)
    with pytest.raises(EntityNotFoundError):
        queries.get_transaction(OTHER_SPACE_ID, result.transaction_id)


def test_queries_expose_real_draft_details_without_posted_entries(ledger_uow_factory) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    commands = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    queries = LedgerQueryService(uow_factory, SqlAlchemyLedgerRepository)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    draft = commands.create_draft(
        DraftCommand(
            space_id=SPACE_ID,
            kind=TransactionKind.INCOME,
            economic_date=date(2026, 7, 3),
            description="Salary draft",
            amount_cents=12_345,
            account_id=account.id,
            category_id=category.id,
            cash_date=date(2026, 7, 4),
        )
    )

    view = queries.get_transaction(SPACE_ID, draft.id)

    assert view.entries == ()
    assert view.draft_details is not None
    assert view.draft_details.amount_cents == 12_345
    assert view.draft_details.account_id == account.id
    assert view.draft_details.category_id == category.id
    assert view.draft_details.cash_date == date(2026, 7, 4)
