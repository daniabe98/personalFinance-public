from __future__ import annotations

from datetime import date

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    DraftCommand,
    IncomeCommand,
    ReverseCommand,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.application.queries import LedgerQueryService
from app.ledger.application.reversal import ReversalService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.transaction import TransactionKind, TransactionStatus
from app.ledger.ports.audit import NullFinancialAuditSink
from tests.support.ledger import SPACE_ID


def test_reversal_is_new_period_event_and_preserves_original_snapshot(
    ledger_uow_factory,
) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    commands = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    reversals = ReversalService(
        uow_factory,
        SqlAlchemyLedgerRepository,
        NullFinancialAuditSink(),
        today=lambda: date(2026, 8, 2),
    )
    queries = LedgerQueryService(uow_factory, SqlAlchemyLedgerRepository)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    original_result = commands.create_income(
        IncomeCommand(
            SPACE_ID,
            account.id,
            category.id,
            800,
            date(2026, 7, 1),
            date(2026, 7, 2),
            "Salary",
            "income-before-reversal",
        )
    )
    replacement = DraftCommand(
        SPACE_ID,
        TransactionKind.INCOME,
        date(2026, 8, 3),
        "Corrected",
        900,
        account.id,
        category.id,
    )
    result = reversals.reverse(
        ReverseCommand(
            SPACE_ID,
            original_result.transaction_id,
            None,
            None,
            "Correction",
            "reverse-1",
            replacement,
        )
    )
    replay = reversals.reverse(
        ReverseCommand(
            SPACE_ID,
            original_result.transaction_id,
            None,
            None,
            "Correction",
            "reverse-1",
            replacement,
        )
    )
    original_view = queries.get_transaction(SPACE_ID, original_result.transaction_id)
    replacement_view = queries.get_transaction(SPACE_ID, result.replacement_transaction_id or "")

    with uow_factory() as unit_of_work:
        repository = SqlAlchemyLedgerRepository(unit_of_work.session)
        original = repository.get_transaction(SPACE_ID, original_result.transaction_id)
        reversal = repository.get_transaction(SPACE_ID, result.transaction_id)
        corrected = repository.get_transaction(SPACE_ID, result.replacement_transaction_id or "")
        balance = repository.account_balance_cents(SPACE_ID, account.id)

    assert original.status is TransactionStatus.VOIDED
    assert original.economic_date == date(2026, 7, 1)
    assert reversal.status is TransactionStatus.POSTED
    assert reversal.economic_date == date(2026, 8, 2)
    assert reversal.cash_date == date(2026, 8, 2)
    assert [entry.signed_cents for entry in reversal.entries] == [
        -entry.signed_cents for entry in original.entries
    ]
    assert corrected.status is TransactionStatus.DRAFT
    assert original_view.replacement_transaction_id == corrected.id
    assert replacement_view.corrected_original_transaction_id == original.id
    assert balance == 0
    assert replay.replayed is True
