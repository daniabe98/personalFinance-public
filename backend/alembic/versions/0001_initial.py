"""Create the V1 relational schema and integrity guards.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op
from app.shared import models_control, models_identity, models_ledger
from app.shared.database import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

del models_control, models_identity, models_ledger

POSTING_GUARD = """
CREATE TRIGGER guard_transaction_posting
BEFORE UPDATE OF state ON transactions
WHEN NEW.state = 'POSTED' AND OLD.state <> 'POSTED'
BEGIN
    SELECT CASE
        WHEN (
            SELECT COUNT(*)
            FROM entries
            WHERE transaction_id = NEW.id AND space_id = NEW.space_id
        ) < 2
        THEN RAISE(ABORT, 'posted transaction requires at least two entries')
    END;
    SELECT CASE
        WHEN (
            SELECT COALESCE(SUM(
                CASE side WHEN 'DEBIT' THEN amount_cents ELSE -amount_cents END
            ), 0)
            FROM entries
            WHERE transaction_id = NEW.id AND space_id = NEW.space_id
        ) <> 0
        THEN RAISE(ABORT, 'posted transaction entries must balance')
    END;
END
"""

AUDIT_UPDATE_GUARD = """
CREATE TRIGGER guard_audit_event_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END
"""

AUDIT_DELETE_GUARD = """
CREATE TRIGGER guard_audit_event_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END
"""

POSTED_ENTRY_INSERT_GUARD = """
CREATE TRIGGER guard_posted_entry_insert
BEFORE INSERT ON entries
WHEN (
    SELECT state FROM transactions
    WHERE id = NEW.transaction_id AND space_id = NEW.space_id
) IN ('POSTED', 'RECONCILED', 'VOIDED')
BEGIN
    SELECT RAISE(ABORT, 'posted entries are immutable');
END
"""

POSTED_ENTRY_UPDATE_GUARD = """
CREATE TRIGGER guard_posted_entry_update
BEFORE UPDATE ON entries
WHEN (
    SELECT state FROM transactions
    WHERE id = OLD.transaction_id AND space_id = OLD.space_id
) IN ('POSTED', 'RECONCILED', 'VOIDED')
BEGIN
    SELECT RAISE(ABORT, 'posted entries are immutable');
END
"""

POSTED_ENTRY_DELETE_GUARD = """
CREATE TRIGGER guard_posted_entry_delete
BEFORE DELETE ON entries
WHEN (
    SELECT state FROM transactions
    WHERE id = OLD.transaction_id AND space_id = OLD.space_id
) IN ('POSTED', 'RECONCILED', 'VOIDED')
BEGIN
    SELECT RAISE(ABORT, 'posted entries are immutable');
END
"""


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    op.execute(POSTING_GUARD)
    op.execute(AUDIT_UPDATE_GUARD)
    op.execute(AUDIT_DELETE_GUARD)
    op.execute(POSTED_ENTRY_INSERT_GUARD)
    op.execute(POSTED_ENTRY_UPDATE_GUARD)
    op.execute(POSTED_ENTRY_DELETE_GUARD)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS guard_posted_entry_delete")
    op.execute("DROP TRIGGER IF EXISTS guard_posted_entry_update")
    op.execute("DROP TRIGGER IF EXISTS guard_posted_entry_insert")
    op.execute("DROP TRIGGER IF EXISTS guard_audit_event_delete")
    op.execute("DROP TRIGGER IF EXISTS guard_audit_event_update")
    op.execute("DROP TRIGGER IF EXISTS guard_transaction_posting")
    Base.metadata.drop_all(bind=op.get_bind())
