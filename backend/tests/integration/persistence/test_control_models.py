from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.shared.models_control import AuditEventRecord, BackupRunRecord


def test_audit_shape_is_append_only(mapped_engine) -> None:
    columns = {column["name"] for column in inspect(mapped_engine).get_columns("audit_events")}
    assert "occurred_at" in columns
    assert "updated_at" not in columns
    assert "deleted_at" not in columns

    with Session(mapped_engine) as session:
        event = AuditEventRecord(
            id="audit-1",
            occurred_at=datetime.now(UTC),
            action="POST_TRANSACTION",
            outcome="SUCCESS",
            correlation_id="corr-1",
        )
        session.add(event)
        session.commit()


def test_only_one_completed_backup_per_domestic_date(mapped_engine) -> None:
    with Session(mapped_engine) as session:
        session.add_all(
            [
                BackupRunRecord(
                    id="b1",
                    backup_date=date(2026, 7, 23),
                    status="COMPLETED",
                    path="/backups/one.sqlite",
                ),
                BackupRunRecord(
                    id="b2",
                    backup_date=date(2026, 7, 23),
                    status="COMPLETED",
                    path="/backups/two.sqlite",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_completed_reconciliation_membership_is_unique(mapped_engine) -> None:
    with mapped_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (id, username, password_hash) VALUES ('u1', 'operator', 'hash');
                """
            )
        )
        connection.execute(
            text("INSERT INTO spaces (id, owner_user_id, name) VALUES ('s1', 'u1', 'Home')")
        )
        connection.execute(
            text(
                """
                INSERT INTO accounts (id, space_id, name, kind)
                VALUES ('a1', 's1', 'Cash', 'ASSET')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO transactions (id, space_id, kind, state, economic_date)
                VALUES ('t1', 's1', 'OPENING', 'DRAFT', '2026-07-23')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO entries
                    (id, space_id, transaction_id, account_id, side, amount_cents)
                VALUES ('e1', 's1', 't1', 'a1', 'DEBIT', 100)
                """
            )
        )
        for reconciliation_id in ("r1", "r2"):
            connection.execute(
                text(
                    """
                    INSERT INTO reconciliations
                        (id, space_id, account_id, cutoff_date, observed_balance_cents, status)
                    VALUES (:id, 's1', 'a1', '2026-07-23', 100, 'COMPLETED')
                    """
                ),
                {"id": reconciliation_id},
            )
        connection.execute(
            text(
                """
                INSERT INTO reconciliation_entries
                    (reconciliation_id, entry_id, space_id, is_completed)
                VALUES ('r1', 'e1', 's1', 1)
                """
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO reconciliation_entries
                        (reconciliation_id, entry_id, space_id, is_completed)
                    VALUES ('r2', 'e1', 's1', 1)
                    """
                )
            )
