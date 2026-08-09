from __future__ import annotations

from datetime import date

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    ExpenseCommand,
    IncomeCommand,
    OpeningCommand,
    TransferCommand,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.transaction import TransactionKind
from app.ledger.ports.audit import NullFinancialAuditSink
from tests.support.ledger import SPACE_ID


def test_opening_income_expense_and_transfer_have_exact_closed_effects(
    ledger_uow_factory,
) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    service = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    bank = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    savings = catalog.create_account(CreateAccount(SPACE_ID, "Savings", AccountKind.ASSET, True))
    liability = catalog.create_account(
        CreateAccount(SPACE_ID, "Mortgage", AccountKind.LIABILITY, True)
    )
    salary = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    food = catalog.create_category(CreateCategory(SPACE_ID, "Food", CategoryKind.EXPENSE))
    economic = date(2026, 7, 1)
    cash = date(2026, 7, 3)

    service.create_opening(OpeningCommand(SPACE_ID, bank.id, 1000, economic, None, "opening-asset"))
    liability_result = service.create_opening(
        OpeningCommand(SPACE_ID, liability.id, 200, economic, None, "opening-liability")
    )
    income_result = service.create_income(
        IncomeCommand(SPACE_ID, bank.id, salary.id, 500, economic, cash, "Salary", "income-1")
    )
    service.create_expense(
        ExpenseCommand(SPACE_ID, bank.id, food.id, 100, economic, cash, "Food", "expense-1")
    )
    transfer_result = service.create_transfer(
        TransferCommand(
            SPACE_ID,
            bank.id,
            savings.id,
            200,
            economic,
            cash,
            "Move",
            "transfer-1",
        )
    )

    with uow_factory() as unit_of_work:
        repository = SqlAlchemyLedgerRepository(unit_of_work.session)
        assert repository.account_balance_cents(SPACE_ID, bank.id) == 1200
        assert repository.account_balance_cents(SPACE_ID, savings.id) == 200
        assert repository.account_balance_cents(SPACE_ID, liability.id) == -200
        liability_opening = repository.get_transaction(SPACE_ID, liability_result.transaction_id)
        income = repository.get_transaction(SPACE_ID, income_result.transaction_id)
        transfer = repository.get_transaction(SPACE_ID, transfer_result.transaction_id)

    assert liability_opening.cash_date is None
    assert income.cash_date == cash
    assert transfer.cash_date == cash
    assert transfer.kind is TransactionKind.TRANSFER
    assert all(entry.category_id is None for entry in transfer.entries)
