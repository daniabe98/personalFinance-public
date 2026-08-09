"""Deterministic helpers shared by ledger tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.transaction import Transaction, TransactionKind
from app.shared.database import Base, create_engine, create_session_factory
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.unit_of_work import UnitOfWorkFactory

SPACE_ID = "space-1"
OTHER_SPACE_ID = "space-2"
ASSET_ID = "asset-1"
ASSET_TWO_ID = "asset-2"
LIABILITY_ID = "liability-1"
EQUITY_ID = "equity-1"
INCOME_ID = "income-1"
EXPENSE_ID = "expense-1"
ECONOMIC_DATE = date(2026, 7, 1)
CASH_DATE = date(2026, 7, 2)


def posted_income(*, transaction_id: str = "income-tx", cents: int = 500) -> Transaction:
    return Transaction.posted(
        transaction_id=transaction_id,
        space_id=SPACE_ID,
        kind=TransactionKind.INCOME,
        economic_date=ECONOMIC_DATE,
        cash_date=CASH_DATE,
        description="Salary",
        entries=(
            Entry.for_account(
                entry_id=f"{transaction_id}-a",
                space_id=SPACE_ID,
                account_id=ASSET_ID,
                side=EntrySide.DEBIT,
                amount_cents=cents,
            ),
            Entry.for_category(
                entry_id=f"{transaction_id}-c",
                space_id=SPACE_ID,
                category_id=INCOME_ID,
                side=EntrySide.CREDIT,
                amount_cents=cents,
            ),
        ),
    )


@pytest.fixture
def ledger_uow_factory(tmp_path: Path) -> Iterator[UnitOfWorkFactory]:
    database_path = tmp_path / "ledger.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory.begin() as session:
        session.add(UserRecord(id="user-1", username="owner", password_hash="test-only"))
        session.flush()
        session.add_all(
            (
                SpaceRecord(id=SPACE_ID, owner_user_id="user-1", name="Personal"),
                SpaceRecord(id=OTHER_SPACE_ID, owner_user_id="user-1", name="Other"),
            )
        )
    try:
        yield UnitOfWorkFactory(session_factory)
    finally:
        engine.dispose()
