from __future__ import annotations

from datetime import date
from typing import cast

import pytest

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
from app.ledger.domain.errors import InvalidLifecycleError
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

    asset_result = service.create_opening(
        OpeningCommand(SPACE_ID, bank.id, 1000, economic, "  Initial asset  ", "opening-asset")
    )
    liability_result = service.create_opening(
        OpeningCommand(
            SPACE_ID,
            liability.id,
            200,
            economic,
            "  Initial liability  ",
            "opening-liability",
        )
    )
    income_result = service.create_income(
        IncomeCommand(SPACE_ID, bank.id, salary.id, 500, economic, cash, "  Salary  ", "income-1")
    )
    expense_result = service.create_expense(
        ExpenseCommand(SPACE_ID, bank.id, food.id, 100, economic, cash, "  Food  ", "expense-1")
    )
    transfer_result = service.create_transfer(
        TransferCommand(
            SPACE_ID,
            bank.id,
            savings.id,
            200,
            economic,
            cash,
            "  Move  ",
            "transfer-1",
        )
    )

    with uow_factory() as unit_of_work:
        repository = SqlAlchemyLedgerRepository(unit_of_work.session)
        assert repository.account_balance_cents(SPACE_ID, bank.id) == 1200
        assert repository.account_balance_cents(SPACE_ID, savings.id) == 200
        assert repository.account_balance_cents(SPACE_ID, liability.id) == -200
        asset_opening = repository.get_transaction(SPACE_ID, asset_result.transaction_id)
        liability_opening = repository.get_transaction(SPACE_ID, liability_result.transaction_id)
        income = repository.get_transaction(SPACE_ID, income_result.transaction_id)
        expense = repository.get_transaction(SPACE_ID, expense_result.transaction_id)
        transfer = repository.get_transaction(SPACE_ID, transfer_result.transaction_id)

    assert asset_opening.description == "Initial asset"
    assert liability_opening.description == "Initial liability"
    assert income.description == "Salary"
    assert expense.description == "Food"
    assert transfer.description == "Move"
    assert liability_opening.cash_date is None
    assert income.cash_date == cash
    assert transfer.cash_date == cash
    assert transfer.kind is TransactionKind.TRANSFER
    assert all(entry.category_id is None for entry in transfer.entries)


@pytest.mark.parametrize("description", [None, "", "   ", "x" * 501])
@pytest.mark.parametrize("operation", ["opening", "income", "expense", "transfer"])
def test_new_posted_operations_reject_invalid_description(
    ledger_uow_factory,
    operation: str,
    description: str | None,
) -> None:
    catalog = CatalogService(ledger_uow_factory, SqlAlchemyLedgerRepository)
    service = FinancialCommandService(
        ledger_uow_factory,
        SqlAlchemyLedgerRepository,
        NullFinancialAuditSink(),
    )
    bank = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    savings = catalog.create_account(CreateAccount(SPACE_ID, "Savings", AccountKind.ASSET, True))
    salary = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    food = catalog.create_category(CreateCategory(SPACE_ID, "Food", CategoryKind.EXPENSE))
    invalid = cast(str, description)
    economic = date(2026, 7, 1)

    with pytest.raises(InvalidLifecycleError, match="description"):
        if operation == "opening":
            service.create_opening(
                OpeningCommand(SPACE_ID, bank.id, 1000, economic, invalid, "invalid-opening")
            )
        elif operation == "income":
            service.create_income(
                IncomeCommand(
                    SPACE_ID,
                    bank.id,
                    salary.id,
                    1000,
                    economic,
                    economic,
                    invalid,
                    "invalid-income",
                )
            )
        elif operation == "expense":
            service.create_expense(
                ExpenseCommand(
                    SPACE_ID,
                    bank.id,
                    food.id,
                    1000,
                    economic,
                    economic,
                    invalid,
                    "invalid-expense",
                )
            )
        else:
            service.create_transfer(
                TransferCommand(
                    SPACE_ID,
                    bank.id,
                    savings.id,
                    1000,
                    economic,
                    economic,
                    invalid,
                    "invalid-transfer",
                )
            )
