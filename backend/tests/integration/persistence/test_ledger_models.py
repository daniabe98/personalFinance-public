from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.models_ledger import AccountRecord, EntryRecord, TransactionRecord


def _spaces(session: Session) -> None:
    session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
    session.flush()
    session.add_all(
        [
            SpaceRecord(id="s1", owner_user_id="u1", name="One"),
            SpaceRecord(id="s2", owner_user_id="u1", name="Two"),
        ]
    )
    session.commit()


def test_money_columns_are_integer_and_transactions_have_no_balance_cache(mapped_engine) -> None:
    inspector = inspect(mapped_engine)
    entry_columns = {column["name"]: column["type"] for column in inspector.get_columns("entries")}
    transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}

    assert entry_columns["amount_cents"].python_type is int
    assert "balance_cents" not in transaction_columns


def test_entry_rejects_cross_space_transaction_or_account(mapped_engine) -> None:
    with Session(mapped_engine) as session:
        _spaces(session)
        session.add(AccountRecord(id="a1", space_id="s1", name="Cash", kind="ASSET"))
        session.add(
            TransactionRecord(
                id="t1",
                space_id="s2",
                kind="TRANSFER",
                state="DRAFT",
                economic_date=date(2026, 7, 23),
            )
        )
        session.commit()
        session.add(
            EntryRecord(
                id="e1",
                space_id="s1",
                transaction_id="t1",
                account_id="a1",
                side="DEBIT",
                amount_cents=100,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_non_positive_or_float_money_is_rejected(mapped_engine) -> None:
    with Session(mapped_engine) as session:
        _spaces(session)
        session.add(AccountRecord(id="a1", space_id="s1", name="Cash", kind="ASSET"))
        session.add(
            TransactionRecord(
                id="t1",
                space_id="s1",
                kind="OPENING",
                state="DRAFT",
                economic_date=date(2026, 7, 23),
            )
        )
        session.commit()
        session.add(
            EntryRecord(
                id="e1",
                space_id="s1",
                transaction_id="t1",
                account_id="a1",
                side="DEBIT",
                amount_cents=0,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
