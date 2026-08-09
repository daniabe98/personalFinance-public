from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.database import create_session_factory
from app.shared.models_control import AuditEventRecord
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.models_ledger import (
    AccountRecord,
    EntryRecord,
    IdempotencyRecord,
    TransactionRecord,
)
from app.shared.unit_of_work import SqlAlchemyUnitOfWork


def test_explicit_commit_persists_the_command(mapped_engine) -> None:
    factory = create_session_factory(mapped_engine)
    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        unit_of_work.session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
        unit_of_work.commit()

    with Session(mapped_engine) as session:
        assert session.get(UserRecord, "u1") is not None


def test_leaving_without_commit_rolls_back(mapped_engine) -> None:
    factory = create_session_factory(mapped_engine)
    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        unit_of_work.session.add(UserRecord(id="u1", username="operator", password_hash="hash"))

    with Session(mapped_engine) as session:
        assert session.get(UserRecord, "u1") is None


def test_exception_rolls_back_and_is_not_swallowed(mapped_engine) -> None:
    factory = create_session_factory(mapped_engine)

    with (
        pytest.raises(RuntimeError, match="injected"),
        SqlAlchemyUnitOfWork(factory) as unit_of_work,
    ):
        unit_of_work.session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
        unit_of_work.session.flush()
        raise RuntimeError("injected")

    with Session(mapped_engine) as session:
        assert session.get(UserRecord, "u1") is None


def test_mid_command_failure_leaves_no_partial_financial_effect(mapped_engine) -> None:
    factory = create_session_factory(mapped_engine)

    with (
        pytest.raises(RuntimeError, match="mid-command"),
        SqlAlchemyUnitOfWork(factory) as unit_of_work,
    ):
        session = unit_of_work.session
        session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
        session.flush()
        session.add(SpaceRecord(id="s1", owner_user_id="u1", name="Home"))
        session.flush()
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
        session.flush()
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
        session.add(
            IdempotencyRecord(
                id="i1",
                space_id="s1",
                command_name="create_opening",
                idempotency_key="request-1",
                payload_hash="a" * 64,
                result_json='{"transaction_id":"t1"}',
                completed_at=datetime.now(UTC),
            )
        )
        session.add(
            AuditEventRecord(
                id="audit-1",
                space_id="s1",
                occurred_at=datetime.now(UTC),
                action="POST_TRANSACTION",
                outcome="SUCCESS",
                correlation_id="request-1",
            )
        )
        session.flush()
        raise RuntimeError("mid-command")

    with Session(mapped_engine) as session:
        for record_type in (
            TransactionRecord,
            EntryRecord,
            IdempotencyRecord,
            AuditEventRecord,
        ):
            count = session.scalar(select(func.count()).select_from(record_type))
            assert count == 0
