"""Deterministic posted finances used to prove a real isolated restore."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    ExpenseCommand,
    IncomeCommand,
    OpeningCommand,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.ports.audit import NullFinancialAuditSink
from app.shared.database import create_engine, create_session_factory
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.unit_of_work import UnitOfWorkFactory

KNOWN_SPACE_ID = "known-space"


@dataclass(frozen=True, slots=True)
class KnownFinanceFingerprint:
    users: int
    spaces: int
    accounts: int
    categories: int
    transactions: int
    entries: int
    asset_balance_cents: int


def seed_known_finances(database: Path) -> KnownFinanceFingerprint:
    engine = create_engine(f"sqlite+pysqlite:///{database.as_posix()}")
    session_factory = create_session_factory(engine)
    unit_of_work_factory = UnitOfWorkFactory(session_factory)
    with session_factory.begin() as session:
        session.add(UserRecord(id="known-user", username="owner", password_hash="test-only"))
        session.flush()
        session.add(
            SpaceRecord(id=KNOWN_SPACE_ID, owner_user_id="known-user", name="Known finances")
        )

    catalog = CatalogService(unit_of_work_factory, SqlAlchemyLedgerRepository)
    asset = catalog.create_account(
        CreateAccount(KNOWN_SPACE_ID, "Household cash", AccountKind.ASSET, True)
    )
    income = catalog.create_category(
        CreateCategory(KNOWN_SPACE_ID, "Known income", CategoryKind.INCOME)
    )
    expense = catalog.create_category(
        CreateCategory(KNOWN_SPACE_ID, "Known expense", CategoryKind.EXPENSE)
    )
    commands = FinancialCommandService(
        unit_of_work_factory,
        SqlAlchemyLedgerRepository,
        NullFinancialAuditSink(),
    )
    commands.create_opening(
        OpeningCommand(
            KNOWN_SPACE_ID,
            asset.id,
            100_000,
            date(2026, 1, 1),
            "Known opening",
            "known-opening",
        )
    )
    commands.create_income(
        IncomeCommand(
            KNOWN_SPACE_ID,
            asset.id,
            income.id,
            50_000,
            date(2026, 1, 2),
            date(2026, 1, 2),
            "Known income",
            "known-income",
        )
    )
    commands.create_expense(
        ExpenseCommand(
            KNOWN_SPACE_ID,
            asset.id,
            expense.id,
            12_500,
            date(2026, 1, 3),
            date(2026, 1, 3),
            "Known expense",
            "known-expense",
        )
    )
    engine.dispose()
    return financial_fingerprint(database)


def financial_fingerprint(database: Path) -> KnownFinanceFingerprint:
    with closing(sqlite3.connect(database)) as connection:
        counts = tuple(
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("users", "spaces", "accounts", "categories", "transactions", "entries")
        )
        balance = connection.execute(
            """
            SELECT coalesce(sum(CASE entries.side WHEN 'DEBIT' THEN entries.amount_cents
                                    ELSE -entries.amount_cents END), 0)
            FROM entries
            JOIN transactions ON transactions.id = entries.transaction_id
            JOIN accounts ON accounts.id = entries.account_id
            WHERE entries.space_id = ?
              AND entries.account_id IS NOT NULL
              AND accounts.kind = 'ASSET'
              AND transactions.state IN ('POSTED', 'RECONCILED', 'VOIDED')
            """,
            (KNOWN_SPACE_ID,),
        ).fetchone()[0]
    return KnownFinanceFingerprint(*counts, asset_balance_cents=int(balance))


__all__ = (
    "KNOWN_SPACE_ID",
    "KnownFinanceFingerprint",
    "financial_fingerprint",
    "seed_known_finances",
)
