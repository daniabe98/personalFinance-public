from __future__ import annotations

from datetime import date

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    DraftCommand,
    ExpenseCommand,
    IncomeCommand,
    OpeningCommand,
    ReverseCommand,
    TransferCommand,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.application.reversal import ReversalService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.transaction import TransactionKind
from app.ledger.ports.audit import NullFinancialAuditSink
from app.reporting.adapters.sql_queries import SqlAlchemyReportingLedgerReader
from app.reporting.application.queries import ReportQueryService
from app.reporting.domain.dtos import ReportInterval
from tests.support.ledger import SPACE_ID


def test_reports_use_exact_dates_and_preserve_cross_period_reversal(ledger_uow_factory) -> None:
    uow_factory = ledger_uow_factory
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    commands = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    reversals = ReversalService(
        uow_factory,
        SqlAlchemyLedgerRepository,
        NullFinancialAuditSink(),
        today=lambda: date(2026, 2, 5),
    )
    reports = ReportQueryService(uow_factory, SqlAlchemyReportingLedgerReader)
    bank = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    savings = catalog.create_account(CreateAccount(SPACE_ID, "Savings", AccountKind.ASSET, True))
    income_category = catalog.create_category(
        CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME)
    )
    expense_category = catalog.create_category(
        CreateCategory(SPACE_ID, "Food", CategoryKind.EXPENSE)
    )
    commands.create_opening(
        OpeningCommand(SPACE_ID, bank.id, 2000, date(2026, 1, 1), None, "opening")
    )
    income = commands.create_income(
        IncomeCommand(
            SPACE_ID,
            bank.id,
            income_category.id,
            1000,
            date(2026, 1, 10),
            date(2026, 1, 11),
            "Salary",
            "income",
        )
    )
    commands.create_expense(
        ExpenseCommand(
            SPACE_ID,
            bank.id,
            expense_category.id,
            300,
            date(2026, 1, 12),
            date(2026, 1, 13),
            "Food",
            "expense",
        )
    )
    commands.create_transfer(
        TransferCommand(
            SPACE_ID,
            bank.id,
            savings.id,
            400,
            date(2026, 1, 14),
            date(2026, 1, 14),
            "Move",
            "transfer",
        )
    )
    draft = commands.create_draft(
        DraftCommand(
            SPACE_ID,
            TransactionKind.INCOME,
            date(2026, 1, 20),
            "Draft",
            999,
            bank.id,
            income_category.id,
        )
    )
    assert draft.entries == ()
    reversals.reverse(
        ReverseCommand(
            SPACE_ID,
            income.transaction_id,
            date(2026, 2, 5),
            date(2026, 2, 5),
            "Correction",
            "reverse-income",
        )
    )

    january = ReportInterval(SPACE_ID, date(2026, 1, 1), date(2026, 1, 31))
    february = ReportInterval(SPACE_ID, date(2026, 2, 1), date(2026, 2, 28))
    combined = ReportInterval(SPACE_ID, date(2026, 1, 1), date(2026, 2, 28))

    january_economic = reports.economic(january)
    february_economic = reports.economic(february)
    combined_economic = reports.economic(combined)
    january_cash = reports.cash_flow(january)
    february_cash = reports.cash_flow(february)
    combined_cash = reports.cash_flow(combined)
    january_net_worth = reports.net_worth(SPACE_ID, date(2026, 1, 31))
    february_net_worth = reports.net_worth(SPACE_ID, date(2026, 2, 28))

    assert (
        january_economic.income_cents,
        january_economic.expense_cents,
        january_economic.result_cents,
    ) == (1000, 300, 700)
    assert (
        february_economic.income_cents,
        february_economic.expense_cents,
        february_economic.result_cents,
    ) == (-1000, 0, -1000)
    assert (
        combined_economic.income_cents,
        combined_economic.expense_cents,
        combined_economic.result_cents,
    ) == (0, 300, -300)
    assert (
        january_cash.receipts_cents,
        january_cash.payments_cents,
        january_cash.net_cash_flow_cents,
    ) == (1000, 300, 700)
    assert (
        february_cash.receipts_cents,
        february_cash.payments_cents,
        february_cash.net_cash_flow_cents,
    ) == (-1000, 0, -1000)
    assert (
        combined_cash.receipts_cents,
        combined_cash.payments_cents,
        combined_cash.net_cash_flow_cents,
    ) == (0, 300, -300)
    assert january_net_worth.net_worth_cents == 2700
    assert february_net_worth.net_worth_cents == 1700
    assert all(value == int(value) for value in (january_net_worth.assets_cents,))
